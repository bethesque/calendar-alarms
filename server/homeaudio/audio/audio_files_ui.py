from contextlib import contextmanager
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from homeaudio.audio.audio_files import AudioFileManager, AudioFileNotFound, AudioLibrary, InvalidAudioFileName, default_libraries

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

@contextmanager
def http_errors():
    try:
        yield
    except InvalidAudioFileName as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AudioFileNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))

class AudioFilesRoutes:
    def __init__(self, libraries: list[AudioLibrary] | None = None):
        self.libraries = {library.slug: library for library in (libraries or default_libraries())}
        self.router = APIRouter()
        self.router.add_api_route("/audio-files", self.index, methods=["GET"], response_class=HTMLResponse)
        self.router.add_api_route("/audio-files/{slug}", self.list_files, methods=["GET"], response_class=HTMLResponse, name="audio_files")
        self.router.add_api_route("/audio-files/{slug}", self.upload_files, methods=["POST"])
        self.router.add_api_route("/audio-files/{slug}/{file_name}", self.get_file, methods=["GET"])
        self.router.add_api_route("/audio-files/{slug}/{file_name}", self.delete_file, methods=["DELETE"])
        self.router.add_api_route("/audio-files/{slug}/{file_name}/toggle", self.toggle_file, methods=["POST"])

    def _manager(self, slug: str) -> AudioFileManager:
        library = self.libraries.get(slug)
        if not library:
            raise HTTPException(status_code=404, detail=f"Unknown audio library {slug}")
        return AudioFileManager(library)

    def index(self, request: Request):
        return RedirectResponse(url=str(request.url_for("audio_files", slug=next(iter(self.libraries)))))

    def list_files(self, request: Request, slug: str):
        manager = self._manager(slug)
        error = None if manager.directory_exists() else f"Directory {manager.library.directory} does not exist"
        return templates.TemplateResponse(
            request=request,
            name="audio_files.html",
            context={
                "library": manager.library,
                "libraries": list(self.libraries.values()),
                "files": manager.list_files(),
                "accept": ",".join(sorted(manager.library.allowed_extensions)),
                "error": error,
            },
        )

    async def upload_files(self, slug: str, files: list[UploadFile]):
        manager = self._manager(slug)
        contents = [(upload.filename, await upload.read()) for upload in files]
        with http_errors():
            return {"uploaded": manager.save(contents)}

    def get_file(self, slug: str, file_name: str):
        with http_errors():
            return FileResponse(self._manager(slug).existing_path(file_name), media_type="audio/mpeg")

    def delete_file(self, slug: str, file_name: str):
        with http_errors():
            self._manager(slug).delete(file_name)
        return {"deleted": file_name}

    def toggle_file(self, slug: str, file_name: str):
        with http_errors():
            enabled = self._manager(slug).toggle(file_name)
        return {"name": file_name, "enabled": enabled}
