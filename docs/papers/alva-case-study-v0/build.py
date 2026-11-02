"""Optional readable HTML compilation; writes only requested presentation output."""
import argparse
import json
from pathlib import Path
import re
import shutil

import markdown
from check import check

HERE = Path(__file__).resolve().parent


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    check()
    output = args.output.resolve()
    if output == HERE or HERE in output.parents:
        raise SystemExit("Use an output directory outside the normative paper sources")
    output.mkdir(parents=True, exist_ok=True)
    (output / "figures").mkdir(exist_ok=True)
    for image in (HERE / "figures").glob("*.svg"):
        shutil.copyfile(image, output / "figures" / image.name)
    shutil.copyfile(HERE / "evidence.json", output / "evidence.json")
    base = json.loads((HERE / "evidence.json").read_bytes())["canonical_base"]
    style = """body{max-width:960px;margin:3rem auto;padding:0 1.4rem;font:18px/1.65 Georgia,serif;color:#17212e}
    h1,h2,h3{font-family:Arial,sans-serif;line-height:1.25}h1{font-size:2rem}h2{margin-top:2.4rem}
    img{max-width:100%;height:auto}table{border-collapse:collapse;width:100%;font:14px/1.5 Arial,sans-serif}
    th,td{border:1px solid #ccd3dd;padding:8px;vertical-align:top}th{background:#edf3fa}
    code{font-size:.82em;overflow-wrap:anywhere}pre{white-space:pre-wrap;background:#f4f6f8;padding:1rem}
    a{color:#154f9c}nav{font:14px Arial,sans-serif;border-bottom:1px solid #ccd3dd;padding-bottom:1rem}
    @media print{body{max-width:none;margin:0;font-size:11pt}nav{display:none}img,table{break-inside:avoid}}
    """
    for name in ("manuscript", "references", "evidence", "README"):
        body = markdown.markdown((HERE / (name + ".md")).read_text(encoding="utf-8"), extensions=["tables", "fenced_code"])
        body = re.sub(r'href="(manuscript|references|evidence|README)\.md(?=[#"])',
                      lambda m: 'href="' + m[1] + '.html', body)
        body = body.replace('href="../../../', 'href="https://github.com/zkidp/alva-core/blob/' + base + '/')
        document = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        document += '<title>ALVA case-study draft — ' + name + '</title><style>' + style + '</style></head><body>'
        document += '<nav><a href="manuscript.html">Manuscript</a> · <a href="references.html">References</a> · <a href="evidence.html">Evidence</a> · <a href="README.html">Reproduction</a></nav>' + body + '</body></html>'
        (output / (name + ".html")).write_text(document, encoding="utf-8")
    print("Compiled four HTML documents and three SVGs to", output)
