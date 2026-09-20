// 用 esbuild/vite/webpack 等现代编译器的解析会更稳，但不一定需要
// 这里用最直接的办法：把 import 行转为变量声明，这样 Node vm 可解析
const fs = require('fs')
const path = process.argv[2]
const src = fs.readFileSync(path, 'utf8')
const m = src.match(/<script setup>([\s\S]*?)<\/script>/)
if (!m) { console.log('No <script setup>'); process.exit(1) }

let code = m[1]
// 把 import 全替换成占位符 const
code = code.replace(/^import\s+.*$/gm, '// import-stub')

try {
  new (require('vm').Script)(code, { filename: path })
  console.log('OK:', path, '(' + code.split('\n').length + ' lines)')
} catch(e) {
  console.log('ERROR parsing', path)
  console.log(e.stack.split('\n').slice(0,5).join('\n'))
  process.exit(1)
}
