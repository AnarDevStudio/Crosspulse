import sys
sys.path.append("../src")
from crosspulse import Crosspulse

bridgeConnect = Crosspulse(mode="connect")
bridgeConnect.register("py_kare", lambda x: x ** 2)
bridgeConnect.connect("./test.js")
result = bridgeConnect.call("js_add")
print(result)  

bridgeListen = Crosspulse(mode="listen")
bridgeListen.register("py_add", lambda a, b: a + b)
bridgeListen.listen()