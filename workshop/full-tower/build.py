"""Current full-tower development entrypoint; ships authored floors 1-20 with 200-floor capacity."""
import argparse
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'chapter-one/tools'))
from build_configurable_candidate import build

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets-from',type=Path,required=True,
                        help='Verified native candidate with BUILD-REPORT.json')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--site',type=Path,required=True)
    args=parser.parse_args()
    import chapterkit
    extension=chapterkit.load(ROOT/'full-tower/content/floors11-20.json')
    print(build(args.assets_from,args.output,args.site,
                ROOT/'chapter-one/content/settings-catalog-20250402.json',extension=extension))
