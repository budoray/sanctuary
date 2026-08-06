(function(){const n=document.createElement("link").relList;if(n&&n.supports&&n.supports("modulepreload"))return;for(const e of document.querySelectorAll('link[rel="modulepreload"]'))i(e);new MutationObserver(e=>{for(const t of e)if(t.type==="childList")for(const o of t.addedNodes)o.tagName==="LINK"&&o.rel==="modulepreload"&&i(o)}).observe(document,{childList:!0,subtree:!0});function c(e){const t={};return e.integrity&&(t.integrity=e.integrity),e.referrerPolicy&&(t.referrerPolicy=e.referrerPolicy),e.crossOrigin==="use-credentials"?t.credentials="include":e.crossOrigin==="anonymous"?t.credentials="omit":t.credentials="same-origin",t}function i(e){if(e.ep)return;e.ep=!0;const t=c(e);fetch(e.href,t)}})();const s=document.getElementById("app");if(!s)throw new Error("Missing #app container");function a(){const r=document.getElementById("splash");r&&(r.classList.add("hidden"),setTimeout(()=>r.remove(),600))}function l(){const r=document.createElement("div");r.className="placeholder-panel",r.innerHTML=`
    <h1>Sanctuary</h1>
    <p>The realm is being rebuilt from the ground up.</p>
    <p class="muted">Top-down OSRIC tactical RPG · solo & party play · human or engine DM</p>
    <footer class="licence">
      Sanctuary is an independent product published under the OSRIC 3.0 Third-Party License
      and is not affiliated with Mythmere Games LLC.
    </footer>
  `,s.appendChild(r)}l();a();
//# sourceMappingURL=index-Dwlg9I2V.js.map
