from pydantic import BaseModel


class ChunkStatusResponse(BaseModel):
    document_id: int
    chunk_count: int
    embedded_count: int
    status: str
