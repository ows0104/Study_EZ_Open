"""Validated format and retrieval settings for private question creation."""
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class PersonalQuestionSettings(BaseModel):
    format: Literal["basic", "cloze", "list", "ox", "mcq", "multi_select", "matching", "sequence"] = "basic"
    retrieval_direction: Literal["direct", "reverse", "mechanism", "discrimination", "integration", "sequence", "trap"] = "direct"
    mcq_mode: Literal["none", "recall_first", "comparison"] = "none"
    answer_units: list[str] = Field(default_factory=list, max_length=100)
    options: list[dict[str, str]] = Field(default_factory=list, max_length=100)
    correct_option_ids: list[str] = Field(default_factory=list, max_length=100)
    answer_pairs: list[dict[str, str]] = Field(default_factory=list, max_length=100)
    correct_order: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_settings(self):
        self.answer_units = [value.strip() for value in self.answer_units if value.strip()]
        if self.format in {"mcq", "multi_select"}:
            self.options = [{"id": item.get("id", "").strip(), "text": item.get("text", "").strip()}
                            for item in self.options]
            ids = [item["id"] for item in self.options]
            self.correct_option_ids = [value.strip() for value in self.correct_option_ids]
            if (len(ids) < 2 or len(set(ids)) != len(ids) or not all(ids)
                    or not all(item["text"] for item in self.options)):
                raise ValueError("서로 다른 ID와 내용이 있는 보기를 2개 이상 입력해 주세요.")
            if (not self.correct_option_ids or len(set(self.correct_option_ids)) != len(self.correct_option_ids)
                    or not set(self.correct_option_ids) <= set(ids)
                    or (self.format == "mcq" and len(self.correct_option_ids) != 1)):
                raise ValueError("객관식 정답은 보기 ID 중 하나, 복수 선택은 하나 이상 지정해 주세요.")
            if self.mcq_mode == "none":
                self.mcq_mode = "comparison"
        else:
            self.mcq_mode, self.options, self.correct_option_ids = "none", [], []
        if self.format == "matching":
            self.answer_pairs = [{"left": item.get("left", "").strip(), "right": item.get("right", "").strip()}
                                 for item in self.answer_pairs]
            if (len(self.answer_pairs) < 2 or not all(item["left"] and item["right"] for item in self.answer_pairs)
                    or len({item["left"] for item in self.answer_pairs}) != len(self.answer_pairs)
                    or len({item["right"] for item in self.answer_pairs}) != len(self.answer_pairs)):
                raise ValueError("중복 없이 왼쪽·오른쪽 항목을 2쌍 이상 입력해 주세요.")
        else:
            self.answer_pairs = []
        if self.format == "sequence":
            self.correct_order = [value.strip() for value in self.correct_order]
            if len(self.correct_order) < 2 or not all(self.correct_order) or len(set(self.correct_order)) != len(self.correct_order):
                raise ValueError("서로 다른 순서 항목을 정답 순으로 2개 이상 입력해 주세요.")
        else:
            self.correct_order = []
        return self
