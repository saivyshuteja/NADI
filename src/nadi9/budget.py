from nadi9.config.settings import Settings


class BudgetExceeded(RuntimeError):
    pass


class BudgetManager:
    def __init__(self, settings: Settings):
        self.max_model = settings.max_model_calls
        self.max_tool = settings.max_tool_calls

    def check(self, model_calls: int, tool_calls: int) -> None:
        if model_calls > self.max_model:
            raise BudgetExceeded(f"model call budget exceeded: {model_calls}/{self.max_model}")
        if tool_calls > self.max_tool:
            raise BudgetExceeded(f"tool call budget exceeded: {tool_calls}/{self.max_tool}")

    def remaining_model(self, model_calls: int) -> int:
        return max(0, self.max_model - model_calls)

    def remaining_tool(self, tool_calls: int) -> int:
        return max(0, self.max_tool - tool_calls)

    def can_model(self, model_calls: int) -> bool:
        return model_calls < self.max_model

    def can_tool(self, tool_calls: int) -> bool:
        return tool_calls < self.max_tool
