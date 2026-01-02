from .coap_device import CoapDevice

def create(device_name: str) -> CoapDevice:
    if device_name == "philips_hu15xx":
        from devices import philips
        return philips.Hu1508()
    raise ValueError(f"Unknown device type: {device_name}")
