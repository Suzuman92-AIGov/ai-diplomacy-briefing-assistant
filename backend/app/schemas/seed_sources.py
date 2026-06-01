from pydantic import BaseModel


class BatchSeedIngestRequest(BaseModel):
    seed_names: list[str]
