"""Platform IO integration; driver-specific queue checks remain in the adapter."""
from .runtime import get_policy


async def send(driver, message, route_key, metadata):
    from src.platform_io.types import DeliveryStatus
    policy = get_policy()
    with policy.output(message.message_id):
        entry = await policy.platform_check(message, route_key, driver)
        policy.platform_result(entry, 'submitted')
        try:
            receipt = await driver.send_message(message=message, route_key=route_key, metadata=metadata)
        except BaseException:
            policy.platform_result(entry, 'unknown')
            raise
        policy.platform_result(entry, 'confirmed' if receipt.status == DeliveryStatus.SENT else 'unknown')
        return receipt
