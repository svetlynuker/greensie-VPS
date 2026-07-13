from typing import Any

from pydantic import BaseModel


class NastaveniVstup(BaseModel):
    # libovolná JSON hodnota (objekt, seznam, řetězec…)
    hodnota: Any
