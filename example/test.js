import Crosspulse from "../src/crosspulse.js";

const bridgeListen = new Crosspulse("listen");
bridgeListen.register("js_add", () => { return "from js: Hello World"; });
bridgeListen.listen();

const bridgeConnect = new Crosspulse("connect");
bridgeConnect.connect("./test.py");
bridgeConnect.call("py_add", 5, 10).then(result => {}).catch(err => {});