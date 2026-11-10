"""Hardened SEXTA-FEIRA wrapper; the original script is in upstream-original/."""
import argparse
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description='Download unchanged official OpenAI checkpoint files')
    parser.add_argument('model', choices=('124M', '355M'))
    parser.add_argument('--models-dir', type=Path, default=Path('models'))
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from sexta_feira.weights import download_weights
    manifest = download_weights(args.models_dir, args.model)
    print('Verified official model: %s (%d files)' % (args.model, len(manifest['files'])))


if __name__ == '__main__':
    main()
