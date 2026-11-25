var UZIP;
"use strict";
var __getOwnPropNames = Object.getOwnPropertyNames;
var __commonJS = (cb, mod) => function __require() {
  try {
    return mod || (0, cb[__getOwnPropNames(cb)[0]])((mod = { exports: {} }).exports, mod), mod.exports;
  } catch (e) {
    throw mod = 0, e;
  }
};

// ../../../node_modules/.pnpm/@resvg+resvg-wasm@2.6.2/node_modules/@resvg/resvg-wasm/index.js
var require_resvg_wasm = __commonJS({
  "../../../node_modules/.pnpm/@resvg+resvg-wasm@2.6.2/node_modules/@resvg/resvg-wasm/index.js"(exports2, module2) {
    "use strict";
    var __defProp = Object.defineProperty;
    var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
    var __getOwnPropNames2 = Object.getOwnPropertyNames;
    var __hasOwnProp = Object.prototype.hasOwnProperty;
    var __export = (target, all) => {
      for (var name in all)
        __defProp(target, name, { get: all[name], enumerable: true });
    };
    var __copyProps = (to, from, except, desc) => {
      if (from && typeof from === "object" || typeof from === "function") {
        for (let key of __getOwnPropNames2(from))
          if (!__hasOwnProp.call(to, key) && key !== except)
            __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
      }
      return to;
    };
    var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);
    var wasm_binding_exports = {};
    __export(wasm_binding_exports, {
      Resvg: () => Resvg2,
      initWasm: () => initWasm
    });
    module2.exports = __toCommonJS(wasm_binding_exports);
    var wasm;
    var heap = new Array(128).fill(void 0);
    heap.push(void 0, null, true, false);
    var heap_next = heap.length;
    function addHeapObject(obj) {
      if (heap_next === heap.length)
        heap.push(heap.length + 1);
      const idx = heap_next;
      heap_next = heap[idx];
      heap[idx] = obj;
      return idx;
    }
    function getObject(idx) {
      return heap[idx];
    }
    function dropObject(idx) {
      if (idx < 132)
        return;
      heap[idx] = heap_next;
      heap_next = idx;
    }
    function takeObject(idx) {
      const ret = getObject(idx);
      dropObject(idx);
      return ret;
    }
    var WASM_VECTOR_LEN = 0;
    var cachedUint8Memory0 = null;
    function getUint8Memory0() {
      if (cachedUint8Memory0 === null || cachedUint8Memory0.byteLength === 0) {
        cachedUint8Memory0 = new Uint8Array(wasm.memory.buffer);
      }
      return cachedUint8Memory0;
    }
    var cachedTextEncoder = typeof TextEncoder !== "undefined" ? new TextEncoder("utf-8") : { encode: () => {
      throw Error("TextEncoder not available");
    } };
    var encodeString = typeof cachedTextEncoder.encodeInto === "function" ? function(arg, view) {
      return cachedTextEncoder.encodeInto(arg, view);
    } : function(arg, view) {
      const buf = cachedTextEncoder.encode(arg);
      view.set(buf);
      return {
        read: arg.length,
        written: buf.length
      };
    };
    function passStringToWasm0(arg, malloc, realloc) {
      if (realloc === void 0) {
        const buf = cachedTextEncoder.encode(arg);
        const ptr2 = malloc(buf.length, 1) >>> 0;
        getUint8Memory0().subarray(ptr2, ptr2 + buf.length).set(buf);
        WASM_VECTOR_LEN = buf.length;
        return ptr2;
      }
      let len = arg.length;
      let ptr = malloc(len, 1) >>> 0;
      const mem = getUint8Memory0();
      let offset = 0;
      for (; offset < len; offset++) {
        const code = arg.charCodeAt(offset);
        if (code > 127)
          break;
        mem[ptr + offset] = code;
      }
      if (offset !== len) {
        if (offset !== 0) {
          arg = arg.slice(offset);
        }
        ptr = realloc(ptr, len, len = offset + arg.length * 3, 1) >>> 0;
        const view = getUint8Memory0().subarray(ptr + offset, ptr + len);
        const ret = encodeString(arg, view);
        offset += ret.written;
        ptr = realloc(ptr, len, offset, 1) >>> 0;
      }
      WASM_VECTOR_LEN = offset;
      return ptr;
    }
    function isLikeNone(x) {
      return x === void 0 || x === null;
    }
    var cachedInt32Memory0 = null;
    function getInt32Memory0() {
      if (cachedInt32Memory0 === null || cachedInt32Memory0.byteLength === 0) {
        cachedInt32Memory0 = new Int32Array(wasm.memory.buffer);
      }
      return cachedInt32Memory0;
    }
    var cachedTextDecoder = typeof TextDecoder !== "undefined" ? new TextDecoder("utf-8", { ignoreBOM: true, fatal: true }) : { decode: () => {
      throw Error("TextDecoder not available");
    } };
    if (typeof TextDecoder !== "undefined") {
      cachedTextDecoder.decode();
    }
    function getStringFromWasm0(ptr, len) {
      ptr = ptr >>> 0;
      return cachedTextDecoder.decode(getUint8Memory0().subarray(ptr, ptr + len));
    }
    function _assertClass(instance, klass) {
      if (!(instance instanceof klass)) {
        throw new Error(`expected instance of ${klass.name}`);
      }
      return instance.ptr;
    }
    function handleError(f, args) {
      try {
        return f.apply(this, args);
      } catch (e) {
        wasm.__wbindgen_exn_store(addHeapObject(e));
      }
    }
    var BBoxFinalization = typeof FinalizationRegistry === "undefined" ? { register: () => {
    }, unregister: () => {
    } } : new FinalizationRegistry((ptr) => wasm.__wbg_bbox_free(ptr >>> 0));
    var BBox = class _BBox {
      static __wrap(ptr) {
        ptr = ptr >>> 0;
        const obj = Object.create(_BBox.prototype);
        obj.__wbg_ptr = ptr;
        BBoxFinalization.register(obj, obj.__wbg_ptr, obj);
        return obj;
      }
      __destroy_into_raw() {
        const ptr = this.__wbg_ptr;
        this.__wbg_ptr = 0;
        BBoxFinalization.unregister(this);
        return ptr;
      }
      free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_bbox_free(ptr);
      }
      /**
      * @returns {number}
      */
      get x() {
        const ret = wasm.__wbg_get_bbox_x(this.__wbg_ptr);
        return ret;
      }
      /**
      * @param {number} arg0
      */
      set x(arg0) {
        wasm.__wbg_set_bbox_x(this.__wbg_ptr, arg0);
      }
      /**
      * @returns {number}
      */
      get y() {
        const ret = wasm.__wbg_get_bbox_y(this.__wbg_ptr);
        return ret;
      }
      /**
      * @param {number} arg0
      */
      set y(arg0) {
        wasm.__wbg_set_bbox_y(this.__wbg_ptr, arg0);
      }
      /**
      * @returns {number}
      */
      get width() {
        const ret = wasm.__wbg_get_bbox_width(this.__wbg_ptr);
        return ret;
      }
      /**
      * @param {number} arg0
      */
      set width(arg0) {
        wasm.__wbg_set_bbox_width(this.__wbg_ptr, arg0);
      }
      /**
      * @returns {number}
      */
      get height() {
        const ret = wasm.__wbg_get_bbox_height(this.__wbg_ptr);
        return ret;
      }
      /**
      * @param {number} arg0
      */
      set height(arg0) {
        wasm.__wbg_set_bbox_height(this.__wbg_ptr, arg0);
      }
    };
    var RenderedImageFinalization = typeof FinalizationRegistry === "undefined" ? { register: () => {
    }, unregister: () => {
    } } : new FinalizationRegistry((ptr) => wasm.__wbg_renderedimage_free(ptr >>> 0));
    var RenderedImage = class _RenderedImage {
      static __wrap(ptr) {
        ptr = ptr >>> 0;
        const obj = Object.create(_RenderedImage.prototype);
        obj.__wbg_ptr = ptr;
        RenderedImageFinalization.register(obj, obj.__wbg_ptr, obj);
        return obj;
      }
      __destroy_into_raw() {
        const ptr = this.__wbg_ptr;
        this.__wbg_ptr = 0;
        RenderedImageFinalization.unregister(this);
        return ptr;
      }
      free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_renderedimage_free(ptr);
      }
      /**
      * Get the PNG width
      * @returns {number}
      */
      get width() {
        const ret = wasm.renderedimage_width(this.__wbg_ptr);
        return ret >>> 0;
      }
      /**
      * Get the PNG height
      * @returns {number}
      */
      get height() {
        const ret = wasm.renderedimage_height(this.__wbg_ptr);
        return ret >>> 0;
      }
      /**
      * Write the image data to Uint8Array
      * @returns {Uint8Array}
      */
      asPng() {
        try {
          const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
          wasm.renderedimage_asPng(retptr, this.__wbg_ptr);
          var r0 = getInt32Memory0()[retptr / 4 + 0];
          var r1 = getInt32Memory0()[retptr / 4 + 1];
          var r2 = getInt32Memory0()[retptr / 4 + 2];
          if (r2) {
            throw takeObject(r1);
          }
          return takeObject(r0);
        } finally {
          wasm.__wbindgen_add_to_stack_pointer(16);
        }
      }
      /**
      * Get the RGBA pixels of the image
      * @returns {Uint8Array}
      */
      get pixels() {
        const ret = wasm.renderedimage_pixels(this.__wbg_ptr);
        return takeObject(ret);
      }
    };
    var ResvgFinalization = typeof FinalizationRegistry === "undefined" ? { register: () => {
    }, unregister: () => {
    } } : new FinalizationRegistry((ptr) => wasm.__wbg_resvg_free(ptr >>> 0));
    var Resvg = class {
      __destroy_into_raw() {
        const ptr = this.__wbg_ptr;
        this.__wbg_ptr = 0;
        ResvgFinalization.unregister(this);
        return ptr;
      }
      free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_resvg_free(ptr);
      }
      /**
      * @param {Uint8Array | string} svg
      * @param {string | undefined} [options]
      * @param {Array<any> | undefined} [custom_font_buffers]
      */
      constructor(svg, options, custom_font_buffers) {
        try {
          const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
          var ptr0 = isLikeNone(options) ? 0 : passStringToWasm0(options, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
          var len0 = WASM_VECTOR_LEN;
          wasm.resvg_new(retptr, addHeapObject(svg), ptr0, len0, isLikeNone(custom_font_buffers) ? 0 : addHeapObject(custom_font_buffers));
          var r0 = getInt32Memory0()[retptr / 4 + 0];
          var r1 = getInt32Memory0()[retptr / 4 + 1];
          var r2 = getInt32Memory0()[retptr / 4 + 2];
          if (r2) {
            throw takeObject(r1);
          }
          this.__wbg_ptr = r0 >>> 0;
          return this;
        } finally {
          wasm.__wbindgen_add_to_stack_pointer(16);
        }
      }
      /**
      * Get the SVG width
      * @returns {number}
      */
      get width() {
        const ret = wasm.resvg_width(this.__wbg_ptr);
        return ret;
      }
      /**
      * Get the SVG height
      * @returns {number}
      */
      get height() {
        const ret = wasm.resvg_height(this.__wbg_ptr);
        return ret;
      }
      /**
      * Renders an SVG in Wasm
      * @returns {RenderedImage}
      */
      render() {
        try {
          const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
          wasm.resvg_render(retptr, this.__wbg_ptr);
          var r0 = getInt32Memory0()[retptr / 4 + 0];
          var r1 = getInt32Memory0()[retptr / 4 + 1];
          var r2 = getInt32Memory0()[retptr / 4 + 2];
          if (r2) {
            throw takeObject(r1);
          }
          return RenderedImage.__wrap(r0);
        } finally {
          wasm.__wbindgen_add_to_stack_pointer(16);
        }
      }
      /**
      * Output usvg-simplified SVG string
      * @returns {string}
      */
      toString() {
        let deferred1_0;
        let deferred1_1;
        try {
          const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
          wasm.resvg_toString(retptr, this.__wbg_ptr);
          var r0 = getInt32Memory0()[retptr / 4 + 0];
          var r1 = getInt32Memory0()[retptr / 4 + 1];
          deferred1_0 = r0;
          deferred1_1 = r1;
          return getStringFromWasm0(r0, r1);
        } finally {
          wasm.__wbindgen_add_to_stack_pointer(16);
          wasm.__wbindgen_free(deferred1_0, deferred1_1, 1);
        }
      }
      /**
      * Calculate a maximum bounding box of all visible elements in this SVG.
      *
      * Note: path bounding box are approx values.
      * @returns {BBox | undefined}
      */
      innerBBox() {
        const ret = wasm.resvg_innerBBox(this.__wbg_ptr);
        return ret === 0 ? void 0 : BBox.__wrap(ret);
      }
      /**
      * Calculate a maximum bounding box of all visible elements in this SVG.
      * This will first apply transform.
      * Similar to `SVGGraphicsElement.getBBox()` DOM API.
      * @returns {BBox | undefined}
      */
      getBBox() {
        const ret = wasm.resvg_getBBox(this.__wbg_ptr);
        return ret === 0 ? void 0 : BBox.__wrap(ret);
      }
      /**
      * Use a given `BBox` to crop the svg. Currently this method simply changes
      * the viewbox/size of the svg and do not move the elements for simplicity
      * @param {BBox} bbox
      */
      cropByBBox(bbox) {
        _assertClass(bbox, BBox);
        wasm.resvg_cropByBBox(this.__wbg_ptr, bbox.__wbg_ptr);
      }
      /**
      * @returns {Array<any>}
      */
      imagesToResolve() {
        try {
          const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
          wasm.resvg_imagesToResolve(retptr, this.__wbg_ptr);
          var r0 = getInt32Memory0()[retptr / 4 + 0];
          var r1 = getInt32Memory0()[retptr / 4 + 1];
          var r2 = getInt32Memory0()[retptr / 4 + 2];
          if (r2) {
            throw takeObject(r1);
          }
          return takeObject(r0);
        } finally {
          wasm.__wbindgen_add_to_stack_pointer(16);
        }
      }
      /**
      * @param {string} href
      * @param {Uint8Array} buffer
      */
      resolveImage(href, buffer) {
        try {
          const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
          const ptr0 = passStringToWasm0(href, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
          const len0 = WASM_VECTOR_LEN;
          wasm.resvg_resolveImage(retptr, this.__wbg_ptr, ptr0, len0, addHeapObject(buffer));
          var r0 = getInt32Memory0()[retptr / 4 + 0];
          var r1 = getInt32Memory0()[retptr / 4 + 1];
          if (r1) {
            throw takeObject(r0);
          }
        } finally {
          wasm.__wbindgen_add_to_stack_pointer(16);
        }
      }
    };
    async function __wbg_load(module22, imports) {
      if (typeof Response === "function" && module22 instanceof Response) {
        if (typeof WebAssembly.instantiateStreaming === "function") {
          try {
            return await WebAssembly.instantiateStreaming(module22, imports);
          } catch (e) {
            if (module22.headers.get("Content-Type") != "application/wasm") {
              console.warn("`WebAssembly.instantiateStreaming` failed because your server does not serve wasm with `application/wasm` MIME type. Falling back to `WebAssembly.instantiate` which is slower. Original error:\n", e);
            } else {
              throw e;
            }
          }
        }
        const bytes = await module22.arrayBuffer();
        return await WebAssembly.instantiate(bytes, imports);
      } else {
        const instance = await WebAssembly.instantiate(module22, imports);
        if (instance instanceof WebAssembly.Instance) {
          return { instance, module: module22 };
        } else {
          return instance;
        }
      }
    }
    function __wbg_get_imports() {
      const imports = {};
      imports.wbg = {};
      imports.wbg.__wbg_new_28c511d9baebfa89 = function(arg0, arg1) {
        const ret = new Error(getStringFromWasm0(arg0, arg1));
        return addHeapObject(ret);
      };
      imports.wbg.__wbindgen_memory = function() {
        const ret = wasm.memory;
        return addHeapObject(ret);
      };
      imports.wbg.__wbg_buffer_12d079cc21e14bdb = function(arg0) {
        const ret = getObject(arg0).buffer;
        return addHeapObject(ret);
      };
      imports.wbg.__wbg_newwithbyteoffsetandlength_aa4a17c33a06e5cb = function(arg0, arg1, arg2) {
        const ret = new Uint8Array(getObject(arg0), arg1 >>> 0, arg2 >>> 0);
        return addHeapObject(ret);
      };
      imports.wbg.__wbindgen_object_drop_ref = function(arg0) {
        takeObject(arg0);
      };
      imports.wbg.__wbg_new_63b92bc8671ed464 = function(arg0) {
        const ret = new Uint8Array(getObject(arg0));
        return addHeapObject(ret);
      };
      imports.wbg.__wbg_values_839f3396d5aac002 = function(arg0) {
        const ret = getObject(arg0).values();
        return addHeapObject(ret);
      };
      imports.wbg.__wbg_next_196c84450b364254 = function() {
        return handleError(function(arg0) {
          const ret = getObject(arg0).next();
          return addHeapObject(ret);
        }, arguments);
      };
      imports.wbg.__wbg_done_298b57d23c0fc80c = function(arg0) {
        const ret = getObject(arg0).done;
        return ret;
      };
      imports.wbg.__wbg_value_d93c65011f51a456 = function(arg0) {
        const ret = getObject(arg0).value;
        return addHeapObject(ret);
      };
      imports.wbg.__wbg_instanceof_Uint8Array_2b3bbecd033d19f6 = function(arg0) {
        let result;
        try {
          result = getObject(arg0) instanceof Uint8Array;
        } catch (_) {
          result = false;
        }
        const ret = result;
        return ret;
      };
      imports.wbg.__wbindgen_string_get = function(arg0, arg1) {
        const obj = getObject(arg1);
        const ret = typeof obj === "string" ? obj : void 0;
        var ptr1 = isLikeNone(ret) ? 0 : passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        var len1 = WASM_VECTOR_LEN;
        getInt32Memory0()[arg0 / 4 + 1] = len1;
        getInt32Memory0()[arg0 / 4 + 0] = ptr1;
      };
      imports.wbg.__wbg_new_16b304a2cfa7ff4a = function() {
        const ret = new Array();
        return addHeapObject(ret);
      };
      imports.wbg.__wbindgen_string_new = function(arg0, arg1) {
        const ret = getStringFromWasm0(arg0, arg1);
        return addHeapObject(ret);
      };
      imports.wbg.__wbg_push_a5b05aedc7234f9f = function(arg0, arg1) {
        const ret = getObject(arg0).push(getObject(arg1));
        return ret;
      };
      imports.wbg.__wbg_length_c20a40f15020d68a = function(arg0) {
        const ret = getObject(arg0).length;
        return ret;
      };
      imports.wbg.__wbg_set_a47bac70306a19a7 = function(arg0, arg1, arg2) {
        getObject(arg0).set(getObject(arg1), arg2 >>> 0);
      };
      imports.wbg.__wbindgen_throw = function(arg0, arg1) {
        throw new Error(getStringFromWasm0(arg0, arg1));
      };
      return imports;
    }
    function __wbg_init_memory(imports, maybe_memory) {
    }
    function __wbg_finalize_init(instance, module22) {
      wasm = instance.exports;
      __wbg_init.__wbindgen_wasm_module = module22;
      cachedInt32Memory0 = null;
      cachedUint8Memory0 = null;
      return wasm;
    }
    async function __wbg_init(input) {
      if (wasm !== void 0)
        return wasm;
      if (typeof input === "undefined") {
        input = new URL("index_bg.wasm", void 0);
      }
      const imports = __wbg_get_imports();
      if (typeof input === "string" || typeof Request === "function" && input instanceof Request || typeof URL === "function" && input instanceof URL) {
        input = fetch(input);
      }
      __wbg_init_memory(imports);
      const { instance, module: module22 } = await __wbg_load(await input, imports);
      return __wbg_finalize_init(instance, module22);
    }
    var dist_default = __wbg_init;
    var initialized2 = false;
    var initWasm = async (module_or_path) => {
      if (initialized2) {
        throw new Error("Already initialized. The `initWasm()` function can be used only once.");
      }
      await dist_default(await module_or_path);
      initialized2 = true;
    };
    var Resvg2 = class extends Resvg {
      /**
       * @param {Uint8Array | string} svg
       * @param {ResvgRenderOptions | undefined} options
       */
      constructor(svg, options) {
        if (!initialized2)
          throw new Error("Wasm has not been initialized. Call `initWasm()` function.");
        const font = options == null ? void 0 : options.font;
        if (!!font && isCustomFontsOptions(font)) {
          const serializableOptions = {
            ...options,
            font: {
              ...font,
              fontBuffers: void 0
            }
          };
          super(svg, JSON.stringify(serializableOptions), font.fontBuffers);
        } else {
          super(svg, JSON.stringify(options));
        }
      }
    };
    function isCustomFontsOptions(value) {
      return Object.prototype.hasOwnProperty.call(value, "fontBuffers");
    }
  }
});

// src/cli.ts
var import_fs6 = require("fs");
var import_path6 = require("path");

// src/svg.ts
var import_fs = require("fs");
var import_path = require("path");
var resvgWasm = require_resvg_wasm();
var initialized = false;
async function ensureInit() {
  if (initialized) return;
  const wasmPath = (0, import_path.join)(__dirname, "resvg.wasm");
  const wasmBuffer = (0, import_fs.readFileSync)(wasmPath);
  await resvgWasm.initWasm(wasmBuffer);
  initialized = true;
}
async function svgToPng(svgData, targetWidth) {
  await ensureInit();
  const resvg = new resvgWasm.Resvg(svgData, {
    fitTo: { mode: "width", value: targetWidth }
  });
  const rendered = resvg.render();
  return Buffer.from(rendered.asPng());
}

// src/icns.ts
var import_fs3 = require("fs");
var import_path3 = require("path");

// src/vips.ts
var import_fs2 = require("fs");
var import_path2 = require("path");

// src/retry.ts
function isMemoryAllocationError(err) {
  const message = err instanceof Error ? `${err.name}: ${err.message}` : String(err);
  const code = err == null ? void 0 : err.code;
  if (code === "ENOMEM") {
    return true;
  }
  return /could not allocate memory|out of memory|cannot allocate|cannot enlarge memory|enlarge memory arrays|memory access out of bounds|array buffer allocation failed|WebAssembly\.Memory|\bENOMEM\b|\bOOM\b/i.test(
    message
  );
}
var defaultSleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function retryOnAllocationFailure(fn, options = {}) {
  const attempts = options.attempts ?? 12;
  const baseDelayMs = options.baseDelayMs ?? 200;
  const maxDelayMs = options.maxDelayMs ?? 2500;
  const sleep = options.sleep ?? defaultSleep;
  const random = options.random ?? Math.random;
  let lastError;
  for (let attempt = 0; attempt < attempts; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastError = err;
      if (!isMemoryAllocationError(err) || attempt === attempts - 1) {
        throw err;
      }
      const ceiling = Math.min(maxDelayMs, baseDelayMs * 2 ** attempt);
      await sleep(Math.floor(random() * ceiling));
    }
  }
  throw lastError;
}

// src/log.ts
var NAMESPACE = "icons";
function isEnabled() {
  const spec = process.env.DEBUG;
  if (!spec) {
    return false;
  }
  let result = false;
  for (const raw of spec.split(/[\s,]+/)) {
    if (!raw) {
      continue;
    }
    const negate = raw.startsWith("-");
    const pattern = negate ? raw.slice(1) : raw;
    const matches = pattern === "*" || pattern === NAMESPACE || pattern.endsWith("*") && NAMESPACE.startsWith(pattern.slice(0, -1));
    if (matches) {
      result = !negate;
    }
  }
  return result;
}
var enabled = isEnabled();
function debug(message) {
  if (enabled) {
    process.stderr.write(`  ${NAMESPACE} ${message}
`);
  }
}

// src/vips.ts
var VipsFactory = require((0, import_path2.join)(__dirname, "vips-node.js"));
var vipsPromise = null;
function getVips() {
  if (vipsPromise == null) {
    vipsPromise = initVips().catch((err) => {
      vipsPromise = null;
      throw err;
    });
  }
  return vipsPromise;
}
async function initVips() {
  const wasmBuffer = (0, import_fs2.readFileSync)((0, import_path2.join)(__dirname, "vips.wasm"));
  debug("vips: initializing wasm-vips (1 GiB shared memory)");
  const vips = await retryOnAllocationFailure(
    () => VipsFactory({
      dynamicLibraries: [],
      instantiateWasm: (imports, receiveInstance) => {
        WebAssembly.instantiate(wasmBuffer, imports).then((result) => {
          receiveInstance(result.instance, result.module);
        });
        return {};
      }
    })
  );
  debug("vips: ready");
  return vips;
}
async function resizeWithLanczos(imageBuffer, targetSize) {
  const vips = await getVips();
  let thumb = null;
  let squared = null;
  let padded = null;
  try {
    thumb = vips.Image.thumbnailBuffer(imageBuffer, targetSize, {
      height: targetSize,
      size: vips.Size.both
    });
    if (thumb.width === targetSize && thumb.height === targetSize) {
      return Buffer.from(thumb.writeToBuffer(".png"));
    }
    squared = thumb.hasAlpha() ? thumb : thumb.bandjoin(255);
    padded = squared.gravity("centre", targetSize, targetSize, {
      extend: "background",
      background: [0, 0, 0, 0]
    });
    return Buffer.from(padded.writeToBuffer(".png"));
  } finally {
    if (padded) padded.delete();
    if (squared && squared !== thumb) squared.delete();
    if (thumb) thumb.delete();
  }
}

// src/png.ts
var PNG_SIGNATURE = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
function isPng(data) {
  return data.length >= 8 && data.subarray(0, 8).equals(PNG_SIGNATURE);
}
function readPngSize(data) {
  if (data.length < 24 || !isPng(data) || data.toString("ascii", 12, 16) !== "IHDR") {
    throw new Error("Input is not a valid PNG (missing signature or IHDR chunk)");
  }
  return { width: data.readUInt32BE(16), height: data.readUInt32BE(20) };
}

// src/icns.ts
var ICNS_ENTRIES = [
  { osType: "icp4", size: 16 },
  { osType: "icp5", size: 32 },
  { osType: "icp6", size: 64 },
  { osType: "ic07", size: 128 },
  { osType: "ic08", size: 256 },
  { osType: "ic09", size: 512 },
  { osType: "ic10", size: 1024 },
  { osType: "ic11", size: 32 },
  // 16@2x
  { osType: "ic12", size: 64 },
  // 32@2x
  { osType: "ic13", size: 256 },
  // 128@2x
  { osType: "ic14", size: 512 }
  // 256@2x
];
function packIcns(frames) {
  const chunks = frames.flatMap(({ osType, png }) => {
    const hdr = Buffer.allocUnsafe(8);
    Buffer.from(osType, "ascii").copy(hdr, 0);
    hdr.writeUInt32BE(8 + png.length, 4);
    return [hdr, png];
  });
  const body = Buffer.concat(chunks);
  const fileHeader = Buffer.allocUnsafe(8);
  Buffer.from("icns", "ascii").copy(fileHeader, 0);
  fileHeader.writeUInt32BE(8 + body.length, 4);
  return Buffer.concat([fileHeader, body]);
}
async function createIcns(inputBuffer, outputDir) {
  const { width, height } = readPngSize(inputBuffer);
  const sourceSize = Math.max(width, height);
  const entries = ICNS_ENTRIES.filter((e) => e.size <= sourceSize);
  if (entries.length === 0) {
    throw new Error(`Source image is too small to build an ICNS (need at least 16px, got ${sourceSize}px)`);
  }
  const uniqueSizes = [...new Set(entries.map((e) => e.size))];
  const pngBySize = /* @__PURE__ */ new Map();
  await Promise.all(
    uniqueSizes.map(async (size) => {
      pngBySize.set(size, await resizeWithLanczos(inputBuffer, size));
    })
  );
  const frames = entries.map(({ osType, size }) => ({ osType, png: pngBySize.get(size) }));
  (0, import_fs3.writeFileSync)((0, import_path3.join)(outputDir, "icon.icns"), packIcns(frames));
}

// src/ico.ts
var import_fs4 = require("fs");
var import_path4 = require("path");
var ICO_SIZES = [16, 24, 32, 48, 64, 128, 256];
function packIco(frames) {
  const count = frames.length;
  let offset = 6 + count * 16;
  const header = Buffer.allocUnsafe(6);
  header.writeUInt16LE(0, 0);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(count, 4);
  const dir = frames.map(({ size, png }) => {
    const entry = Buffer.allocUnsafe(16);
    const w = size === 256 ? 0 : size;
    entry.writeUInt8(w, 0);
    entry.writeUInt8(w, 1);
    entry.writeUInt8(0, 2);
    entry.writeUInt8(0, 3);
    entry.writeUInt16LE(1, 4);
    entry.writeUInt16LE(32, 6);
    entry.writeUInt32LE(png.length, 8);
    entry.writeUInt32LE(offset, 12);
    offset += png.length;
    return entry;
  });
  return Buffer.concat([header, ...dir, ...frames.map((f) => f.png)]);
}
async function createIco(inputBuffer, outputDir) {
  const { width, height } = readPngSize(inputBuffer);
  const sourceSize = Math.max(width, height);
  const sizes = ICO_SIZES.filter((s) => s <= sourceSize);
  if (sizes.length === 0) {
    sizes.push(sourceSize);
  }
  const frames = await Promise.all(
    sizes.map(async (size) => ({ size, png: await resizeWithLanczos(inputBuffer, size) }))
  );
  (0, import_fs4.writeFileSync)((0, import_path4.join)(outputDir, "icon.ico"), packIco(frames));
}

// src/linux.ts
var import_fs5 = require("fs");
var import_path5 = require("path");
var LINUX_SIZES = [16, 24, 32, 48, 64, 128, 256, 512];
async function createLinuxSet(inputBuffer, outputDir) {
  const { width, height } = readPngSize(inputBuffer);
  const sourceSize = Math.max(width, height);
  const sizes = LINUX_SIZES.filter((s) => s <= sourceSize);
  if (sizes.length === 0) {
    sizes.push(sourceSize);
  }
  for (const size of sizes) {
    const resized = await resizeWithLanczos(inputBuffer, size);
    (0, import_fs5.writeFileSync)((0, import_path5.join)(outputDir, `${size}x${size}.png`), resized);
  }
}

// src/icns-input.ts
var META_TYPES = /* @__PURE__ */ new Set(["info", "TOC ", "icnV", "name"]);
var MASK_TYPES = /* @__PURE__ */ new Set(["s8mk", "l8mk", "h8mk", "t8mk"]);
var RAW_TYPES = /* @__PURE__ */ new Set([
  "ICON",
  "ICN#",
  "icm#",
  "icm4",
  "icm8",
  "ics#",
  "ics4",
  "ics8",
  "is32",
  "icl4",
  "icl8",
  "il32",
  "ich#",
  "ich4",
  "ich8",
  "ih32",
  "it32",
  "icp4",
  "icp5",
  "icp6"
]);
var ICNS_MAGIC = "icns";
var JP2_BOX_MAGIC = Buffer.from([0, 0, 0, 12, 106, 80, 32, 32, 13, 10, 135, 10]);
var J2K_CODESTREAM_MAGIC = Buffer.from([255, 79, 255, 81]);
var ARGB_MAGIC = Buffer.from("ARGB", "ascii");
function startsWith(data, magic) {
  return data.length >= magic.length && data.subarray(0, magic.length).equals(magic);
}
function classify(ostype, payload) {
  if (isPng(payload)) return "png";
  if (startsWith(payload, JP2_BOX_MAGIC) || startsWith(payload, J2K_CODESTREAM_MAGIC)) return "jp2";
  if (startsWith(payload, ARGB_MAGIC)) return "argb";
  if (META_TYPES.has(ostype)) return "meta";
  if (MASK_TYPES.has(ostype)) return "mask";
  if (RAW_TYPES.has(ostype)) return "raw";
  return "unknown";
}
function extractLargestPngFromIcns(data) {
  const entries = [];
  if (data.length < 8 || data.toString("ascii", 0, 4) !== ICNS_MAGIC) {
    debug("icns: not a valid ICNS container (bad magic)");
    return { png: null, entries };
  }
  let best = null;
  let offset = 8;
  while (offset + 8 <= data.length) {
    const ostype = data.toString("ascii", offset, offset + 4);
    const entryLen = data.readUInt32BE(offset + 4);
    if (entryLen < 8) {
      debug(`icns: stopping at offset ${offset}: invalid entry length ${entryLen}`);
      break;
    }
    const payloadStart = offset + 8;
    const payloadEnd = offset + entryLen;
    if (payloadEnd > data.length) {
      debug(`icns: truncated entry "${ostype}" at offset ${offset} (declares ${entryLen} bytes, ${data.length - offset} remain)`);
      break;
    }
    const payload = data.subarray(payloadStart, payloadEnd);
    const encoding = classify(ostype, payload);
    const info = { ostype, length: payload.length, encoding };
    if (encoding === "png" && payload.length >= 24) {
      info.width = payload.readUInt32BE(16);
      info.height = payload.readUInt32BE(20);
      if (best == null || info.width > best.width) {
        best = { png: payload, width: info.width };
      }
    }
    entries.push(info);
    offset += entryLen;
  }
  debug(`icns: parsed ${entries.length} entries [${entries.map((e) => `${e.ostype}:${e.encoding}${e.width ? `:${e.width}x${e.height}` : ""}`).join(", ")}]`);
  if (best != null) {
    debug(`icns: selected largest PNG frame (${best.width}px)`);
    return { png: best.png, entries };
  }
  debug("icns: no PNG frame found");
  return { png: null, entries };
}
function describeIcnsEntries(entries) {
  if (entries.length === 0) return "none";
  return entries.map((e) => `${e.ostype}(${e.encoding}, ${e.length}B${e.width ? `, ${e.width}x${e.height}` : ""})`).join(", ");
}

// src/args.ts
function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (!arg.startsWith("--")) {
      continue;
    }
    const eq = arg.indexOf("=");
    if (eq !== -1) {
      args[arg.slice(2, eq)] = arg.slice(eq + 1);
      continue;
    }
    const key = arg.slice(2);
    const next = argv[i + 1];
    if (next !== void 0 && !next.startsWith("--")) {
      args[key] = next;
      i++;
    } else {
      args[key] = "";
    }
  }
  return args;
}

// src/cli.ts
var VALID_FORMATS = ["icns", "ico", "set"];
var SVG_RASTER_WIDTH = 1024;
async function main() {
  const args = parseArgs(process.argv.slice(2));
  const input = args["input"];
  const format = args["format"];
  const outDir = args["out"];
  if (!input || !format || !outDir) {
    console.error("Usage: node icon-tool.js --input <path> --format <icns|ico|set> --out <dir>");
    process.exit(1);
  }
  if (!VALID_FORMATS.includes(format)) {
    console.error(`Invalid format "${format}". Valid formats: ${VALID_FORMATS.join(", ")}`);
    process.exit(1);
  }
  if (!(0, import_fs6.existsSync)(input)) {
    console.error(`Input file not found: ${input}`);
    process.exit(1);
  }
  (0, import_fs6.mkdirSync)(outDir, { recursive: true });
  const ext = (0, import_path6.extname)(input).toLowerCase();
  debug(`input=${input} format=${format} ext=${ext} out=${outDir}`);
  let pngBuffer;
  if (ext === ".svg") {
    const svgBuffer = (0, import_fs6.readFileSync)(input);
    pngBuffer = await svgToPng(svgBuffer, SVG_RASTER_WIDTH);
  } else if (ext === ".png") {
    pngBuffer = (0, import_fs6.readFileSync)(input);
  } else if (ext === ".icns") {
    const icnsBuffer = (0, import_fs6.readFileSync)(input);
    const { png, entries } = extractLargestPngFromIcns(icnsBuffer);
    if (!png) {
      console.error(
        `Could not extract a PNG frame from ICNS file. Frames found: [${describeIcnsEntries(entries)}]. This toolset can only read PNG-encoded ICNS frames; JPEG2000, ARGB, and legacy raw frames are not supported. Re-export the icon as a PNG/SVG source, or as an ICNS containing a PNG frame.`
      );
      process.exit(1);
    }
    pngBuffer = png;
  } else {
    console.error(`Unsupported input format "${ext}". Supported: .png, .svg, .icns`);
    process.exit(1);
  }
  switch (format) {
    case "icns":
      await createIcns(pngBuffer, outDir);
      break;
    case "ico":
      await createIco(pngBuffer, outDir);
      break;
    case "set":
      await createLinuxSet(pngBuffer, outDir);
      break;
  }
  console.log(`Done: ${format} \u2192 ${outDir}`);
}
main().catch((err) => {
  console.error("Error:", err.message || String(err));
  process.exit(1);
});
