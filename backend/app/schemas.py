from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

Positive = Annotated[int, Field(strict=True, gt=0, le=1000000)]
Nonnegative = Annotated[int, Field(strict=True, ge=0, le=1000000)]
Text = Annotated[str, Field(min_length=1, max_length=100, pattern=r".*\S.*")]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ItemIn(Input):
    name: Text
    category: Annotated[str, Field(min_length=1, max_length=60)]
    condition: Literal["new", "good", "fair"]
    on_hand: Nonnegative


class PickupIn(Input):
    id: UUID
    volunteer_id: Positive


class ReserveIn(Input):
    request_key: UUID
    pickup_id: UUID
    item_id: Positive
    quantity: Positive
