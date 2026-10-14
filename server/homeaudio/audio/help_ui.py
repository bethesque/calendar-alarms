from pathlib import Path
import markdown
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"

class HelpRoutes:
    def __init__(self, docs_dir: Path = DOCS_DIR):
        self.docs_dir = docs_dir
        self.router = APIRouter()
        self.router.add_api_route("", self.show, methods=["GET"], response_class=HTMLResponse, name="docs_index")
        self.router.add_api_route("/{name}", self.show, methods=["GET"], response_class=HTMLResponse, name="docs_page")

    def show(self, request: Request, name: str = "index"):
        path = {p.stem: p for p in self.docs_dir.glob("*.md")}.get(name)
        if not path:
            raise HTTPException(status_code=404, detail=f"Unknown doc {name}")
        md = markdown.Markdown(extensions=["tables", "fenced_code", "toc"])
        content = md.convert(path.read_text())
        title = md.toc_tokens[0]["name"] if md.toc_tokens else name
        help_root = request.url_for("docs_index").path
        back = help_root.rsplit("/", 1)[0] or "/" if name == "index" else help_root
        return templates.TemplateResponse(request=request, name="help.html", context={"title": title, "content": content, "back": back})
