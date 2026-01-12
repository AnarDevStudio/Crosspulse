// Copyright (c) 2026 Crosspulse

// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software.


const { spawn } = require("child_process");
const path = require("path");

class Crosspulse {
  /**
   * Crosspulse - JavaScript ↔ Python Bridge
   * İki yönlü iletişim: Hem dinle, hem çağır
   */
  
  constructor(mode = "connect") {
    /**
     * mode: "connect" = Python'a bağlan ve onun metodlarını çağır
     *       "listen" = Python'dan gelen çağrıları dinle
     */
    this.mode = mode;
    this.handlers = new Map();
    this.process = null;
    this.buffer = "";
    this.callbacks = new Map();
    this.requestId = 0;
  }

  // ==================== CONNECT MODE ====================

  async connect(pythonFile) {
    /**
     * Python scriptine bağlan
     */
    if (this.mode !== "connect") {
      throw new Error("Crosspulse must be in 'connect' mode");
    }

    return new Promise((resolve, reject) => {
      const pyPath = path.resolve(__dirname, pythonFile);
      this.process = spawn("python3", [pyPath]);

      this.process.stdout.on("data", (data) => {
        this.buffer += data.toString();
        
        let lines = this.buffer.split("\n");
        this.buffer = lines.pop() || "";

        for (let line of lines) {
          if (!line.trim()) continue;
          
          try {
            const response = JSON.parse(line);
            
            // Python'dan gelen çağrı cevabı
            if (response.id !== undefined && this.callbacks.has(response.id)) {
              const callback = this.callbacks.get(response.id);
              this.callbacks.delete(response.id);
              
              if (response.success) {
                callback.resolve(response.result);
              } else {
                callback.reject(new Error(response.error));
              }
            }
            
            // Python'dan gelen metod çağrısı
            else if (response.method) {
              this._handleIncomingCall(response);
            }
            
          } catch (err) {
            console.error("JSON parse error:", err);
          }
        }
      });

      this.process.stderr.on("data", (data) => {
        console.error("Python stderr:", data.toString());
      });

      this.process.on("close", (code) => {
        if (code !== 0) {
          reject(new Error(`Python process exited with code ${code}`));
        }
      });

      this.process.on("error", (err) => {
        reject(err);
      });

      // Process hazır
      setTimeout(() => resolve(this), 100);
    });
  }

  call(method, ...args) {
    /**
     * Python'daki bir metodu çağır
     */
    return new Promise((resolve, reject) => {
      if (!this.process) {
        return reject(new Error("Not connected. Call connect() first."));
      }

      const id = this.requestId++;
      this.callbacks.set(id, { resolve, reject });

      const request = {
        id,
        method,
        args,
        kwargs: {}
      };

      this.process.stdin.write(JSON.stringify(request) + "\n");
    });
  }

  disconnect() {
    /**
     * Bağlantıyı kapat
     */
    if (this.process) {
      this.process.kill();
      this.process = null;
    }
  }

  // ==================== LISTENER MODE ====================

  register(methodName, callback) {
    /**
     * Bir metodu kaydet (Python'dan çağrılabilir)
     */
    this.handlers.set(methodName, callback);
    return this;
  }

  listen() {
    /**
     * Python'dan gelen çağrıları dinle (stdin üzerinden)
     */
    if (this.mode !== "listen") {
      throw new Error("Crosspulse must be in 'listen' mode");
    }

    process.stdin.setEncoding('utf8');
    
    process.stdin.on('data', (data) => {
      this.buffer += data.toString();
      
      let lines = this.buffer.split("\n");
      this.buffer = lines.pop() || "";

      for (let line of lines) {
        if (!line.trim()) continue;
        
        try {
          const request = JSON.parse(line);
          this._handleIncomingCall(request);
        } catch (err) {
          console.error("JSON parse error:", err);
        }
      }
    });

    process.stdin.on('end', () => {
      process.exit(0);
    });
  }

  _handleIncomingCall(request) {
    /**
     * Gelen metod çağrısını işle
     */
    const method = request.method;
    const args = request.args || [];
    const id = request.id;

    let response;

    if (this.handlers.has(method)) {
      try {
        const result = this.handlers.get(method)(...args);
        response = { id, success: true, result };
      } catch (err) {
        response = { id, success: false, error: err.message };
      }
    } else {
      response = { id, success: false, error: `Method not found: ${method}` };
    }

    // Cevabı gönder
    if (this.mode === "connect" && this.process) {
      this.process.stdin.write(JSON.stringify(response) + "\n");
    } else if (this.mode === "listen") {
      console.log(JSON.stringify(response));
    }
  }
}

module.exports = Crosspulse;


