"""Small, explicit public-web research. No cookies, credentials, proxy or tool execution."""
from __future__ import annotations
from collections import Counter, OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
from html.parser import HTMLParser
import http.client
import ipaddress
import re
import socket
import ssl
import threading
import time
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, quote_plus, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

AGENT = "SextaFeiraResearch/1.0"
MAX_BYTES = 524288
_DNS_SLOT = threading.BoundedSemaphore(1)


class ResearchUnavailable(RuntimeError):
    pass


class ResearchBusy(ResearchUnavailable):
    pass


def global_unicast(address):
    return address.is_global and not any((address.is_reserved, address.is_multicast,
        address.is_unspecified, address.is_loopback, address.is_link_local,
        getattr(address,"is_site_local",False), getattr(address,"scope_id",None),
        getattr(address,"sixtofour",None), getattr(address,"teredo",None)))


def public_url(url: str) -> str:
    if not isinstance(url, str) or len(url) > 1600 or re.search(r"[\x00-\x20\x7f\\]", url):
        raise ValueError("Informe uma URL HTTPS pública válida, sem espaços.")
    try:
        p = urlsplit(url)
        host = (p.hostname or "").encode("idna").decode("ascii").lower().rstrip(".")
        if p.scheme != "https" or not host or p.username is not None or p.password is not None or p.port not in (None, 443):
            raise ValueError
        private_keys = {"token","accesstoken","authtoken","password","passwd","secret","apikey",
                        "authorization","session","sessionid","signature","credential","credentials",
                        "xamzcredential","xamzsignature","xgoogcredential","xgoogsignature"}
        if any(re.sub(r"[-_]","",key.casefold()) in private_keys for key in parse_qs(p.query,keep_blank_values=True)):
            raise ValueError
        if host in ("localhost", "metadata.google.internal") or host.endswith((".local", ".localhost", ".internal", ".lan", ".home", ".arpa")):
            raise ValueError
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if "." not in host or not re.fullmatch(r"[a-z0-9.-]+", host):
                raise ValueError
        else:
            if not global_unicast(address):
                raise ValueError
        authority = "[" + host + "]" if ":" in host else host
        return urlunsplit(("https", authority, p.path or "/", p.query, ""))
    except (ValueError, UnicodeError):
        raise ValueError("Somente sites HTTPS públicos, sem login na URL ou portas alternativas.") from None


def public_addresses(host: str, deadline: float | None = None) -> list[str]:
    def resolve():
        return socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if deadline is None:
        records = resolve()
    else:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not _DNS_SLOT.acquire(blocking=False):
            raise ResearchUnavailable("Resolução de endereço indisponível agora.")
        completed, outcome = threading.Event(), {}
        def worker():
            try:
                outcome["records"] = resolve()
            except (OSError, ValueError, UnicodeError):
                outcome["failed"] = True
            finally:
                _DNS_SLOT.release()
                completed.set()
        # One timed-out OS lookup cannot create an unbounded number of threads:
        # the slot stays occupied until that lookup actually returns.
        thread = threading.Thread(target=worker, name="sexta-web-dns", daemon=True)
        try:
            thread.start()
        except RuntimeError:
            _DNS_SLOT.release()
            raise ResearchUnavailable("Resolução de endereço indisponível agora.") from None
        if not completed.wait(min(4, remaining)) or outcome.get("failed"):
            raise ResearchUnavailable("Tempo de resolução do endereço esgotado.")
        records = outcome.get("records", [])
    addresses = list(dict.fromkeys(item[4][0] for item in records))
    if not addresses or any(not global_unicast(ipaddress.ip_address(address)) for address in addresses):
        raise ValueError("Destino privado ou reservado bloqueado.")
    return sorted(addresses, key=lambda address: ":" in address)


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address, timeout):
        super().__init__(host, timeout=timeout, context=ssl.create_default_context())
        self.address = address
        self._wire = None
        self._wire_lock = threading.Lock()
        self.expired = False

    def connect(self):
        sock = socket.create_connection((self.address, 443), self.timeout)
        try:
            with self._wire_lock:
                if self.expired:
                    raise TimeoutError("Request deadline expired")
                self.sock = self._context.wrap_socket(sock, server_hostname=self.host,
                                                       do_handshake_on_connect=False)
                self._wire = self.sock
            self.sock.do_handshake()
        except BaseException:
            sock.close()
            raise

    def abort(self):
        with self._wire_lock:
            self.expired = True
            wire = self._wire
        if wire is not None:
            try:
                wire.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            wire.close()


class PublicWeb:
    def __init__(self):
        self._robots = OrderedDict()
        self._last_pages = OrderedDict()

    def fetch(self, url, deadline, *, limit=MAX_BYTES, kinds=("text/html", "text/plain"), respect_robots=False):
        for redirect in range(4):
            url = public_url(url)
            p = urlsplit(url)
            if time.monotonic() >= deadline:
                raise ResearchUnavailable("Tempo de consulta à web esgotado.")
            if respect_robots:
                if not self.allowed(url, deadline):
                    return {"url":url,"status":403,"text":"","type":""}
                origin = "https://" + p.netloc
                self._last_pages[origin] = time.monotonic()
                self._last_pages.move_to_end(origin)
                while len(self._last_pages) > 32:
                    self._last_pages.popitem(last=False)
            addresses = public_addresses(p.hostname, deadline)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ResearchUnavailable("Tempo de consulta à web esgotado.")
            connection = PinnedHTTPS(p.hostname, addresses[0], min(5, remaining))
            response = None
            timer = threading.Timer(remaining, connection.abort)
            timer.daemon = True
            timer.start()
            try:
                connection.request("GET", urlunsplit(("", "", p.path or "/", p.query, "")),
                    headers={"User-Agent": AGENT, "Accept": ",".join(kinds), "Accept-Encoding": "identity", "Connection": "close"})
                response = connection.getresponse()
                if response.status in (301, 302, 303, 307, 308):
                    if redirect == 3:
                        raise ResearchUnavailable("Redirecionamentos excessivos.")
                    url = urljoin(url, response.getheader("Location", ""))
                    continue  # Every redirect is revalidated and pinned to a public IP.
                if response.status != 200:
                    return {"url": url, "status": response.status, "text": "", "type": ""}
                content_type = response.getheader("Content-Type", "").lower()
                if content_type.split(";",1)[0].strip() not in kinds:
                    raise ResearchUnavailable("Formato de página não suportado; use HTML público.")
                if response.getheader("Content-Encoding", "identity").lower() not in ("", "identity"):
                    raise ResearchUnavailable("Página comprimida não suportada nesta integração.")
                declared = response.getheader("Content-Length")
                if declared and (not declared.isdigit() or int(declared) > limit):
                    raise ResearchUnavailable("Página excede o limite de leitura.")
                body = bytearray()
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ResearchUnavailable("Tempo de leitura esgotado.")
                    if connection.sock:
                        connection.sock.settimeout(min(5, remaining))
                    chunk = response.read1(min(65536, limit + 1 - len(body)))
                    if not chunk:
                        break
                    body.extend(chunk)
                    if len(body) > limit:
                        raise ResearchUnavailable("Página excede o limite de leitura.")
                if connection.expired or time.monotonic() >= deadline:
                    raise ResearchUnavailable("Tempo de leitura esgotado.")
                charset = re.search(r"charset\s*=\s*([\w-]+)", content_type)
                encoding = charset.group(1) if charset else "utf-8"
                if encoding not in ("utf-8", "utf8", "iso-8859-1", "windows-1252", "us-ascii"):
                    encoding = "utf-8"
                return {"url": url, "status": 200, "text": body.decode(encoding, "replace"), "type": content_type}
            except (OSError, http.client.HTTPException):
                raise ResearchUnavailable("Não foi possível ler a página pública dentro dos limites da consulta.") from None
            finally:
                timer.cancel()
                if response is not None:
                    response.close()
                connection.close()
        raise ResearchUnavailable("Página indisponível.")

    def allowed(self, url, deadline):
        p = urlsplit(public_url(url))
        origin = "https://" + p.netloc
        cached = self._robots.pop(origin, None)
        if cached and time.monotonic() - cached[0] < 1800:
            fetched_at, parser = cached
        else:
            response = self.fetch(origin + "/robots.txt", min(deadline, time.monotonic() + 4), limit=65536)
            parser = RobotFileParser()
            if response["status"] == 200:
                parser.parse(response["text"].splitlines())
            elif response["status"] in (404, 410):
                parser.parse(["User-agent: *", "Allow: /"])
            else:
                return False
            fetched_at = time.monotonic()
        self._robots[origin] = (fetched_at, parser)
        while len(self._robots) > 32:
            self._robots.popitem(last=False)
        delay = parser.crawl_delay(AGENT) or 0
        rate = parser.request_rate(AGENT)
        if rate and rate.requests > 0:
            delay = max(delay, rate.seconds / rate.requests)
        last = self._last_pages.get(origin)
        return parser.can_fetch(AGENT, url) and (last is None or time.monotonic()-last >= delay)


def cleaned_text(text, limit=12000):
    return " ".join(text.split())[:limit]


def parse_rss(text):
    """Personal RSS result rendering. Feed descriptions never enter the LLM."""
    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        raise ResearchUnavailable("Feed XML com declarações não permitidas.")
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        raise ResearchUnavailable("O buscador não retornou um feed válido.") from None
    results, seen = [], set()
    for item in root.findall("./channel/item")[:20]:
        try:
            url = public_url(item.findtext("link", ""))
        except ValueError:
            continue
        if url not in seen:
            results.append({"url":url,"title":cleaned_text(item.findtext("title", ""),160),"snippet":""})
            seen.add(url)
        if len(results) == 5:
            break
    return results


class PageText(HTMLParser):
    SKIP = {"script", "style", "nav", "header", "footer", "form", "aside", "noscript", "svg", "template"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skipped, self.title, self.in_title, self.parts, self.size = [], "", False, [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skipped.append(tag)
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if self.skipped and tag == self.skipped[-1]:
            self.skipped.pop()
        if tag == "title":
            self.in_title = False

    def handle_data(self, text):
        if not self.skipped:
            if self.in_title:
                self.title += text
            elif self.size < 80000:
                self.parts.append(text)
                self.size += len(text)


def relevant_excerpt(text, query, limit=900):
    text = cleaned_text(text, 80000)
    query = re.sub(r"\bsite:\S+", "", query.casefold())
    terms = set(re.findall(r"\w{4,}", query)) - {"como","para","qual","quais","sobre","what","that","this","documentation","documentação"}
    counts = Counter(re.findall(r"\w{4,}",text.casefold()))
    windows = [text[i:i+limit] for i in range(0, min(len(text), 60000), limit//2)] or [""]
    def score(chunk):
        local = Counter(re.findall(r"\w{4,}",chunk.casefold()))
        return sum(min(local[term],3)/(counts[term]+1) for term in terms)
    return max(windows, key=score)[:limit]


def research_request(message):
    """Only user requests or an explicit UI option select outbound research."""
    match = re.match(r"^/(pesquisar|pesquisa|buscar|site|ler)\s+(.+)$", message.strip(), re.I | re.S)
    if match:
        return {"url" if match[1].lower() in ("site", "ler") else "query": match[2].strip()}
    match = re.match(r"^(?:por favor[, ]+)?(?:pesquise|pesquisa|busque|procure)(?:\s+na\s+(?:web|internet))?\s+(.+)$",message.strip(),re.I | re.S)
    return {"query": match[1].strip()} if match else None


def research_query(query):
    if not isinstance(query,str) or not 2 <= len(query.strip()) <= 320:
        raise ValueError("A pesquisa deve ter entre 2 e 320 caracteres.")
    query = cleaned_text(query, 320)
    if re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?:\d[ .-]?){11,}|\b(?:Bearer\s+\S+|sk-[A-Za-z0-9_-]+)\b",query,re.I) or re.search(r"[A-Za-z0-9_-]{36,}",query):
        raise ValueError("Retire credenciais e identificadores pessoais antes de pesquisar na web.")
    return query


class ResearchEngine:
    def __init__(self, summarizer=None, client=None):
        self.client = client or PublicWeb()
        self.summarizer = summarizer
        self._slot = threading.BoundedSemaphore(1)
        self._cache = OrderedDict()
        self._last = None

    def run(self, *, query=None, url=None):
        if (query is None) == (url is None):
            raise ValueError("Informe apenas query ou url.")
        query = research_query(query) if query is not None else ""
        url = public_url(url) if url is not None else None
        if not self._slot.acquire(blocking=False):
            raise ResearchBusy("Uma pesquisa já está em andamento. Aguarde.")
        try:
            key = (query, url)
            cached = self._cache.get(key)
            if cached and time.monotonic() - cached[0] < 300:
                result = deepcopy(cached[1])
                result["cached"] = True
                return result
            if self._last is not None and time.monotonic() - self._last < 10:
                raise ResearchBusy("Aguarde alguns segundos entre pesquisas.")
            self._last = time.monotonic()
            deadline = time.monotonic() + 22
            if url:
                results = [{"url":url,"title":urlsplit(url).hostname,"snippet":""}]
            else:
                # This endpoint is a personal RSS reader, never a public search service.
                # Only independently fetched publisher pages are supplied to the LLM.
                search_url = "https://www.bing.com/search?q=" + quote_plus(query) + "&format=rss"
                response = self.client.fetch(search_url, min(deadline,time.monotonic()+10),
                    kinds=("text/xml","application/rss+xml","application/xml"),limit=262144)
                if response["status"] != 200:
                    raise ResearchUnavailable("O serviço de busca limitou o acesso. Tente mais tarde ou envie um site público.")
                results = parse_rss(response["text"])
            documents = []
            hosts = set()
            for item in results:
                if time.monotonic() >= deadline or len(documents) == 3:
                    break
                host = urlsplit(item["url"]).hostname
                if host in hosts:
                    continue
                hosts.add(host)
                record = {"url":item["url"],"title":cleaned_text(item["title"],160),
                          "text":cleaned_text(item["snippet"],500),"read":False}
                try:
                    if self.client.allowed(item["url"],deadline):
                        page = self.client.fetch(item["url"],min(deadline,time.monotonic()+6),respect_robots=True)
                        if page["status"] == 200 and not re.search(r"challenge-form|cf-chl-|verify you are human",page["text"],re.I):
                            parser = PageText(); parser.feed(page["text"])
                            text = relevant_excerpt(" ".join(parser.parts),query or item["title"])
                            if len(text) >= 80:
                                record.update(url=page["url"],title=cleaned_text(parser.title or record["title"],160),text=text,read=True)
                except ValueError:
                    if url:
                        raise
                    continue  # Never present a blocked private destination as a source.
                except (OSError, ResearchUnavailable, http.client.HTTPException):
                    pass
                documents.append(record)
            if not documents:
                raise ResearchUnavailable("Não encontrei fontes públicas acessíveis para esta consulta.")
            retrieved = time.monotonic()
            stamp = datetime.now(timezone.utc).isoformat()
            result = self._answer(query or "Resuma o conteúdo desta página.",documents,"site direto" if url else "Bing RSS pessoal",stamp)
            self._cache[key] = (retrieved,deepcopy(result))
            while len(self._cache) > 16:
                self._cache.popitem(last=False)
            return result
        finally:
            self._slot.release()

    def _answer(self, query, documents, provider, stamp):
        readable = [item for item in documents if item["read"]][:2]
        answer, generated = "", False
        if readable and self.summarizer:
            try:
                answer = self.summarizer(query, readable)
                if not isinstance(answer,str):
                    answer = ""
                answer = re.sub(r"\[(\d+)\]",lambda match: match[0] if 1 <= int(match[1]) <= len(readable) else "",answer)
                # Never let model output introduce links or invented source IDs.
                if re.search(r"https?://|www\.|\]\(",answer) or not re.search(r"\[[1-"+str(len(readable))+r"]\]",answer):
                    answer = ""
                for doc in readable:
                    words = re.findall(r"\w+",doc["text"].casefold())
                    quoted = {tuple(words[i:i+6]) for i in range(max(0,len(words)-5))}
                    output = re.findall(r"\w+",answer.casefold())
                    copied = set()
                    for i in range(max(0,len(output)-5)):
                        if tuple(output[i:i+6]) in quoted:
                            copied.update(range(i,i+6))
                    # Leave room for the five-word source title, including when
                    # several separate copied passages occur in one answer.
                    if len(copied) > 20:
                        answer = ""
                generated = bool(answer)
            except (RuntimeError, ValueError, TimeoutError):
                pass
        used = readable if generated else documents[:2]
        if not answer:
            answer = "Fontes disponíveis para consulta. Não foi gerada uma síntese com citações válidas; confira os trechos e os links:"
            for i,item in enumerate(used,1):
                excerpt = " ".join(item["text"].split()[:20])
                answer += f"\n[{i}] {excerpt}" + ("…" if excerpt else "Página sem trecho disponível.")
        answer += "\n\nFontes consultadas:\n"
        for i,item in enumerate(used,1):
            title = " ".join(item["title"].replace("[","").replace("]","").split()[:5])
            answer += f"[{i}] {title}\n{item['url']}\n" + ("Página lida.\n" if item["read"] else "Apenas link; página não lida.\n")
        answer += "Consulta em " + stamp + ". Conteúdo externo pode estar incorreto ou desatualizado."
        return {"reply":answer,"source":"local_model" if generated else "tool","generated":generated,
                "action_executed":True,"tool":"web_research","executed":True,"cached":False,
                "research":{"retrieved_at_utc":stamp,"provider":provider,
                            "sources":[{k:v for k,v in item.items() if k != "text"} for item in used]}}
