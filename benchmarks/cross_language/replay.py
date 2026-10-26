"""Re-evaluate published final code, not model tasks or reference solutions."""
import argparse
import shutil
import tempfile
from pathlib import Path
from common import HERE,load,evaluate
from tasks import TASKS


def main():
    parser=argparse.ArgumentParser();parser.add_argument("binary",type=Path);args=parser.parse_args()
    results=load(HERE/"RESULTS.json")
    with tempfile.TemporaryDirectory(prefix="alva-cl-replay-") as name:
        root=Path(name)
        for row in results:
            slot=row["slot"];arm=row["arm"]
            task=next(t for t in TASKS if t["id"]==row["task"])
            p=root/slot;(p/"src").mkdir(parents=True)
            inputs=load(HERE/"inputs"/(slot+".json"))
            for relative,content in inputs["initial_files"].items():
                target=p/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(content,encoding="utf-8")
            source=HERE/"final"/(slot+(".py" if arm=="A" else ".alva"))
            shutil.copy2(source,p/("program.py" if arm=="A" else "src/task.alva"))
            authority=HERE/"final"/slot/"alva-air"
            if arm=="C" and authority.exists():shutil.copytree(authority,p/"alva-air")
            actual=evaluate(p,arm,task,args.binary.resolve(),root/(slot+"-build"))
            assert actual["status"]==row["final"]["status"],(slot,actual["status"],row["final"]["status"])
            print(slot+" reproduced "+actual["status"],flush=True)


if __name__=="__main__":main()
