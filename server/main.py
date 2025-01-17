import os
from typing import Optional
import aiohttp
import uvicorn
from io import BytesIO
from fastapi import FastAPI, File, HTTPException, Depends, Body, UploadFile
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import Headers
from urllib.parse import urlparse

from models.api import (
    DeleteRequest,
    DeleteResponse,
    QueryRequest,
    QueryResponse,
    UpsertRequest,
    UpsertResponse,
)
from datastore.factory import get_datastore
from services.file import get_document_from_file

bearer_scheme = HTTPBearer()
BEARER_TOKEN = os.environ.get("BEARER_TOKEN")
assert BEARER_TOKEN is not None


def validate_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    if credentials.scheme != "Bearer" or credentials.credentials != BEARER_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    return credentials


app = FastAPI(dependencies=[Depends(validate_token)])
# app.mount("/.well-known", StaticFiles(directory=".well-known"), name="static")

# Create a sub-application, in order to access just the query endpoint in an OpenAPI schema, found at http://0.0.0.0:8000/sub/openapi.json when the app is running locally
sub_app = FastAPI(
    title="Retrieval Plugin API",
    description="A retrieval API for querying and filtering documents based on natural language queries and metadata",
    version="1.0.0",
    servers=[{"url": "https://your-app-url.com"}],
    dependencies=[Depends(validate_token)],
)
app.mount("/sub", sub_app)


@app.post(
    "/upsert-file-link",
    response_model=UpsertResponse,
)
async def upsert_file_link(
    file_link: str = Body(...),
    author: str = Body(...),
    created_at: str = Body(...),
    chunk_size: Optional[int] = Body(default=None),
    chunk_overlap: Optional[int] = Body(default=None),
):
    async with aiohttp.ClientSession() as session:
        async with session.get(file_link) as response:
            file_text = await response.read()
            content_type = response.headers.get('Content-Type')
            url_path = urlparse(file_link).path
            filename = url_path.split('/')[-1] if '/' in url_path else url_path

    bytes_io = BytesIO(file_text)

    # Создание объекта UploadFile
    upload_file = UploadFile(
        file=bytes_io,
        filename=filename,  # замените на подходящее имя файла
        headers=Headers({
            "content-type": content_type,
        })
    )

    document = await get_document_from_file(upload_file)

    try:
        document.metadata.author = author
        document.metadata.url = file_link
        document.metadata.created_at = created_at
        ids = await datastore.upsert([document], chunk_size, chunk_overlap)
        return UpsertResponse(ids=ids)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail=f"str({e})")


@app.post(
    "/upsert-file",
    response_model=UpsertResponse,
)
async def upsert_file(
    file: UploadFile = File(...),
    author: str = Body(...),
    url: Optional[str] = Body(None),
    chunk_size: Optional[int] = Body(default=None),
    chunk_overlap: Optional[int] = Body(default=None),
):
    document = await get_document_from_file(file)

    try:
        document.metadata.author = author
        document.metadata.url = url
        ids = await datastore.upsert([document], chunk_size, chunk_overlap)
        return UpsertResponse(ids=ids)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail=f"str({e})")


@app.post(
    "/upsert",
    response_model=UpsertResponse,
)
async def upsert(
    request: UpsertRequest = Body(...),
):
    try:
        ids = await datastore.upsert(request.documents, request.chunk_size, request.chunk_overlap)
        return UpsertResponse(ids=ids)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail=f"str({e})")


@app.post(
    "/query",
    response_model=QueryResponse,
)
async def query_main(
    request: QueryRequest = Body(...),
):
    results = await datastore.query(
        request.queries,
    )
    return QueryResponse(results=results)


@sub_app.post(
    "/query",
    response_model=QueryResponse,
    # NOTE: We are describing the shape of the API endpoint input due to a current limitation in parsing arrays of objects from OpenAPI schemas. This will not be necessary in the future.
    description="Accepts search query objects array each with query and optional filter. Break down complex questions into sub-questions. Refine results by criteria, e.g. time / source, don't do this often. Split queries if ResponseTooLargeError occurs.",
)
async def query(
    request: QueryRequest = Body(...),
):
    try:
        results = await datastore.query(
            request.queries,
        )
        return QueryResponse(results=results)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


@app.delete(
    "/delete",
    response_model=DeleteResponse,
)
async def delete(
    request: DeleteRequest = Body(...),
):
    if not (request.ids or request.filter or request.delete_all):
        raise HTTPException(
            status_code=400,
            detail="One of ids, filter, or delete_all is required",
        )
    try:
        success = await datastore.delete(
            ids=request.ids,
            filter=request.filter,
            delete_all=request.delete_all,
        )
        return DeleteResponse(success=success)
    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


@app.on_event("startup")
async def startup():
    global datastore
    datastore = await get_datastore()


def start():
    uvicorn.run("server.main:app", host="0.0.0.0", port=8002, reload=True)


if __name__ == "__main__":
    start()