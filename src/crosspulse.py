# Copyright (c) 2026 Crosspulse

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software.


import sys
import json
import threading
import subprocess
from typing import Callable, Dict, Any, Optional

class Crosspulse:
    """
    Crosspulse - Python ↔ JavaScript Bridge
    İki yönlü iletişim: Hem dinle, hem çağır
    """
    
    def __init__(self, mode: str = "listen"):
        """
        mode: "listen" = JS'den gelen çağrıları dinle
              "connect" = JS scriptine bağlan ve onun metodlarını çağır
        """
        self.mode = mode
        self.handlers: Dict[str, Callable] = {}
        self.js_process: Optional[subprocess.Popen] = None
        self.buffer = ""
        self.callbacks: Dict[int, Any] = {}
        self.request_id = 0
        self.lock = threading.Lock()
        
    
    def register(self, method_name: str, callback: Callable):
        """Bir metodu kaydet (JS'den çağrılabilir)"""
        self.handlers[method_name] = callback
        return self
    
    def listen(self):
        """JS'den gelen çağrıları dinle"""
        if self.mode != "listen":
            raise Exception("Crosspulse must be in 'listen' mode")
            
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            
            try:
                request = json.loads(line)
                
                # JS'den gelen çağrı
                if "method" in request:
                    method = request.get("method")
                    args = request.get("args", [])
                    kwargs = request.get("kwargs", {})
                    req_id = request.get("id")
                    
                    if method in self.handlers:
                        result = self.handlers[method](*args, **kwargs)
                        response = {"id": req_id, "success": True, "result": result}
                    else:
                        response = {"id": req_id, "success": False, "error": f"Method not found: {method}"}
                
                # JS'den gelen cevap (biz çağırmıştık)
                elif "id" in request and request["id"] in self.callbacks:
                    callback = self.callbacks.pop(request["id"])
                    if request.get("success"):
                        callback["resolve"](request.get("result"))
                    else:
                        callback["reject"](request.get("error"))
                    continue
                    
            except Exception as e:
                response = {"id": request.get("id"), "success": False, "error": str(e)}
            
            print(json.dumps(response), flush=True)
    
    # ==================== CONNECT MODE ====================
    
    def connect(self, js_file: str):
        """JS scriptine bağlan"""
        if self.mode != "connect":
            raise Exception("Crosspulse must be in 'connect' mode")
        
        self.js_process = subprocess.Popen(
            ["node", js_file],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # Çıktıları dinle
        threading.Thread(target=self._read_js_output, daemon=True).start()
        return self
    
    def _read_js_output(self):
        """JS'den gelen mesajları oku"""
        for line in self.js_process.stdout:
            line = line.strip()
            if not line:
                continue
            
            try:
                response = json.loads(line)
                
                # JS'den gelen çağrı cevabı
                if "id" in response and response["id"] in self.callbacks:
                    callback = self.callbacks.pop(response["id"])
                    if response.get("success"):
                        callback["event"].set()
                        callback["result"] = response.get("result")
                    else:
                        callback["event"].set()
                        callback["error"] = response.get("error")
                
                # JS'den gelen metod çağrısı
                elif "method" in response:
                    method = response.get("method")
                    args = response.get("args", [])
                    req_id = response.get("id")
                    
                    if method in self.handlers:
                        result = self.handlers[method](*args)
                        reply = {"id": req_id, "success": True, "result": result}
                    else:
                        reply = {"id": req_id, "success": False, "error": f"Method not found: {method}"}
                    
                    self.js_process.stdin.write(json.dumps(reply) + "\n")
                    self.js_process.stdin.flush()
                    
            except Exception as e:
                print(f"Error reading JS output: {e}", file=sys.stderr)
    
    def call(self, method: str, *args) -> Any:
        """JS'deki bir metodu çağır"""
        if not self.js_process:
            raise Exception("Not connected. Call connect() first.")
        
        with self.lock:
            req_id = self.request_id
            self.request_id += 1
        
        event = threading.Event()
        callback_data = {"event": event, "result": None, "error": None}
        self.callbacks[req_id] = callback_data
        
        request = {
            "id": req_id,
            "method": method,
            "args": list(args),
            "kwargs": {}
        }
        
        self.js_process.stdin.write(json.dumps(request) + "\n")
        self.js_process.stdin.flush()
        
        # Cevap bekle
        event.wait(timeout=10)
        
        if callback_data["error"]:
            raise Exception(callback_data["error"])
        
        return callback_data["result"]
    
    def disconnect(self):
        """Bağlantıyı kapat"""
        if self.js_process:
            self.js_process.terminate()
            self.js_process.wait()
            self.js_process = None

