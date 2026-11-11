// Security regression: model output must become text, never executable HTML.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.textContent='';this.className='';}
 append(...nodes){this.children.push(...nodes);}
 addEventListener(){}
}
const document={createElement:tag=>new Element(tag),createTextNode:text=>({tag:'#text',textContent:text,children:[]})};
const source=fs.readFileSync(path.join(__dirname,'../sexta_feira/web/app.js'),'utf8');
const context=vm.createContext({document});
vm.runInContext(source.slice(source.indexOf('function appendInline('),source.indexOf('function message(')),context);
const unsafe='<img src=x onerror=alert(1)> **<svg onload=alert(2)>** `literal`\n```html\n<script>alert(3)</script>\n```\n- item\n### Heading';
const rendered=context.renderAnswer(unsafe);
function all(node){return [node,...node.children.flatMap(all)];}
const nodes=all(rendered);
assert(!nodes.some(node=>['img','svg','script','iframe'].includes(node.tag)));
assert(nodes.some(node=>node.tag==='code' && node.textContent==='<script>alert(3)</script>'));
assert(nodes.some(node=>node.tag==='strong' && node.textContent==='<svg onload=alert(2)>'));
assert(nodes.some(node=>node.className==='answer-list-item'));
assert(nodes.some(node=>node.className==='answer-heading'));
const unfinished=context.renderAnswer('```python\nprint("hello")');
assert(all(unfinished).some(node=>node.tag==='code' && node.textContent==='print("hello")'));
console.log('Safe answer rendering: 7 assertions passed');
