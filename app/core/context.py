from contextvars import ContextVar

acc_num_ctx: ContextVar[int] = ContextVar("acc_num")


def get_acc_num() -> int:
    try:
        return acc_num_ctx.get()
    except LookupError:
        raise RuntimeError(
            "acc_num not found in request context"
        )