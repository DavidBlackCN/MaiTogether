"""MaiTogether 交付与身份提示；不建立第二套生活状态。"""
import asyncio


class DeliveryProblem(RuntimeError):
    def __init__(self, state, message):
        self.state = state
        super().__init__(message)


async def deliver(ctx, operation, args):
    try:
        result = await ctx.call_capability('behavior.send_v1', version=1,
                                          operation=operation, args=args, timeout_ms=95000)
    except asyncio.CancelledError:
        raise
    except Exception as error:
        raise DeliveryProblem('unknown', '交付结果待核对：' + str(error)) from error
    if not isinstance(result, dict) or result.get('version') != 1:
        raise DeliveryProblem('unknown', '交付回执不可用，请核对实际结果')
    state = result.get('state')
    if state != 'confirmed':
        raise DeliveryProblem(state if state in ('deferred', 'failed', 'unknown', 'partial') else 'unknown',
                              result.get('reason') or '本次交付未确认成功')
    if operation == 'space' and not result.get('post_id'):
        raise DeliveryProblem('unknown', '平台未返回动态编号，请核对空间')
    return result


def people_context(rows):
    """生日、备注保留；生活模型推断的关系不作为固定身份提示。"""
    return [{k: v for k, v in row.items() if k not in {
        'name', 'relationship', 'relationship_reason', 'intimacy', 'intimacy_mode'
    }} for row in rows]
