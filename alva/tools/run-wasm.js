// 用 Node 内置 WASI 运行 alva 生成的 wasm（wasm32-wasip1）
// 用法: node tools/run-wasm.js <file.wasm>
const { WASI } = require('node:wasi');
const fs = require('node:fs');

const file = process.argv[2];
if (!file) {
  console.error('usage: node tools/run-wasm.js <file.wasm>');
  process.exit(2);
}

const wasi = new WASI({ version: 'preview1' });
const importObject = { wasi_snapshot_preview1: wasi.wasiImport };

WebAssembly.instantiate(fs.readFileSync(file), importObject)
  .then(({ instance }) => {
    wasi.start(instance);
  })
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
