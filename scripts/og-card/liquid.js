// A still frame of the site's liquid behind the card (card.html loads this).
// render.mjs sets the shader source from
// site/src/components/ui/LiquidBackground.tsx; opened by hand, the card shows
// the plain ground instead. It lives outside card.html so the claims gate,
// which counts every digit in the card's markup, has no script to skip.
(function () {
  const frag = window.__LIQUID_FRAGMENT__;
  const canvas = document.getElementById('liquid');
  const gl = frag && canvas.getContext('webgl', { preserveDrawingBuffer: true });
  if (!gl) return;
  const w = (canvas.width = Math.round(innerWidth * 0.75));
  const h = (canvas.height = Math.round(innerHeight * 0.75));
  const shader = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); return s; };
  const p = gl.createProgram();
  gl.attachShader(p, shader(gl.VERTEX_SHADER, 'attribute vec2 aPos; void main() { gl_Position = vec4(aPos, 0.0, 1.0); }'));
  gl.attachShader(p, shader(gl.FRAGMENT_SHADER, frag));
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) return;
  gl.useProgram(p);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const a = gl.getAttribLocation(p, 'aPos');
  gl.enableVertexAttribArray(a);
  gl.vertexAttribPointer(a, 2, gl.FLOAT, false, 0, 0);
  const css = getComputedStyle(document.documentElement);
  const lin = (name) => {
    const hex = css.getPropertyValue(name).trim();
    return [1, 3, 5].map((i) => { const v = parseInt(hex.slice(i, i + 2), 16) / 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
  };
  const u = (n) => gl.getUniformLocation(p, n);
  gl.uniform3fv(u('uDeep'), lin('--raised'));
  gl.uniform3fv(u('uGround'), lin('--card'));
  gl.uniform3fv(u('uRule'), lin('--rule-2'));
  gl.uniform3fv(u('uCool'), lin('--blue'));
  gl.uniform3fv(u('uWarm'), lin('--amber'));
  gl.uniform1f(u('uCap'), 0.014);
  gl.uniform2f(u('uRes'), w, h);
  gl.uniform1f(u('uTime'), 42);
  gl.uniform2f(u('uPointer'), w * 0.8, h * 0.66);
  gl.uniform1f(u('uTouch'), 0.9);
  gl.uniform1f(u('uScroll'), 0);
  gl.viewport(0, 0, w, h);
  gl.drawArrays(gl.TRIANGLES, 0, 3);
})();
