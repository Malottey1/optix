# Vendored files

Downloaded once with curl (never npm). They are served from this folder at runtime, so the page
makes no request to any host other than the one serving the repo. Each licence file sits next to
the code. `tests/test_ui_stack.py` checks that every file in this folder is listed here, and that
each SHA-256 matches.

| File | Package | Version | Source URL (one-time download) | SHA-256 (file as committed) | Licence |
|---|---|---|---|---|---|
| react.mjs | react | 18.3.1 | https://esm.sh/react@18.3.1/es2022/react.bundle.mjs (from https://esm.sh/react@18.3.1?bundle&target=es2022), production build | 6c691dfb36c3d786c21d1f08dfcac3aedae05487eccca408f91fb495e38c2d0c | MIT, LICENSE-react |
| react-dom-client.mjs | react-dom (client) | 18.3.1 | https://esm.sh/react-dom@18.3.1/X-ZXJlYWN0/es2022/client.bundle.mjs (from https://esm.sh/react-dom@18.3.1/client?bundle&target=es2022&external=react), production build | 93f913947677f79c434f1109c6309c8c126548354006bd79ca4659613d57293b | MIT, LICENSE-react-dom |
| htm.mjs | htm | 3.1.1 | https://cdn.jsdelivr.net/npm/htm@3.1.1/dist/htm.module.js | ab33dd3f38059b9be4d5f5350128eefb2356639c4e0bbe9d9e8b3ba75847e9e4 | Apache-2.0, LICENSE-htm |
| tailwindcss-browser.js | @tailwindcss/browser | 4.1.11 | https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4.1.11/dist/index.global.js | 7933e213b39f3434b04eb24d219f279596a9c7d9f7833f7e3a8db3cebe7e69d3 | MIT, LICENSE-tailwindcss |
| LICENSE-react | react | 18.3.1 | https://cdn.jsdelivr.net/npm/react@18.3.1/LICENSE | 52412d7bc7ce4157ea628bbaacb8829e0a9cb3c58f57f99176126bc8cf2bfc85 | |
| LICENSE-react-dom | react-dom | 18.3.1 | https://cdn.jsdelivr.net/npm/react-dom@18.3.1/LICENSE | 52412d7bc7ce4157ea628bbaacb8829e0a9cb3c58f57f99176126bc8cf2bfc85 | |
| LICENSE-htm | htm | 3.1.1 | https://cdn.jsdelivr.net/npm/htm@3.1.1/LICENSE | 740725f7252e750af735d0028cc534970772f513331e9f68150fede8fb3ce00f | |
| LICENSE-tailwindcss | @tailwindcss/browser | 4.1.11 | https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4.1.11/LICENSE | 60e0b68c0f35c078eef3a5d29419d0b03ff84ec1df9c3f9d6e39a519a5ae7985 | |

Changes after download: in react.mjs and react-dom-client.mjs the trailing `//# sourceMappingURL=`
line was removed (it pointed at a map file that is not vendored, and devtools would request it).
SHA-256 of the files as downloaded: react.mjs 2f6da27083fcbd17e548127b10a424c6dd8033720b1734e6f8f0ab9c54d7fbda,
react-dom-client.mjs af1ce9fc13e9e1c88387eea3e6f0cf0e86c89403c5f07f27b7b57e4f2692d4b0. The other files are unchanged.

Imports: react-dom-client.mjs imports only the bare specifier `"react"`, which the import map in
app/index.html resolves to ./vendor/react.mjs. No vendored file imports a URL. The remaining
`http(s)://` strings in these files are XML namespace names, error-decoder links and comments,
never fetched.

The ESM builds of React and ReactDOM worked, so the Preact fallback was not needed.
