(function () {
  /* ---------- tiny util ---------- */
  const $ = id => document.getElementById(id);
  const fetchJSON = u => fetch(u, {credentials: 'same-origin'}).then(r => r.json());
  const fill = (sel, items, blank = true) => {
    if (!sel) return;
    const cur = sel.value;
    sel.innerHTML = '';
    if (blank) sel.appendChild(new Option('---------', ''));
    items.forEach(i => sel.appendChild(new Option(i.text, i.id)));
    if (items.some(i => String(i.id) === String(cur))) sel.value = cur;
    sel.dispatchEvent(new Event('change', { bubbles: true }));
  };

  /* ---------- build base ---------- */
  function getBase() {
    /*  /…/portal/enrollment/add/                 → /…/portal/enrollment/
        /…/portal/enrollment/15/change/          → /…/portal/enrollment/
    */
    return location.pathname
      .replace(/\/add\/?$/, '/')
      .replace(/\/\d+\/change\/?$/, '/');
  }

  /* ---------- wire ---------- */
  function bind(pSel, sSel, cSel, semSel, slotSel, gSel) {
    const base = getBase();                 // ← 修正后的根
    console.log('[enroll v3] base =', base);

    pSel.onchange = () => {
      fill(sSel, []);
      pSel.value &&
        fetchJSON(`${base}related/students/?parent_id=${pSel.value}`)
          .then(d => fill(sSel, d.results));
    };

    cSel.onchange = () => {
      [semSel, slotSel, gSel].forEach(sel => fill(sel, []));
      cSel.value &&
        fetchJSON(`${base}related/semesters/?course_id=${cSel.value}`)
          .then(d => fill(semSel, d.results));
    };

    semSel.onchange = () => {
      [slotSel, gSel].forEach(sel => fill(sel, []));
      if (cSel.value && semSel.value)
        fetchJSON(`${base}related/slots/?course_id=${cSel.value}&semester_id=${semSel.value}`)
          .then(d => fill(slotSel, d.results));
    };

    slotSel.onchange = () => {
      fill(gSel, []);
      slotSel.value &&
        fetchJSON(`${base}related/subgroups/?slot_id=${slotSel.value}`)
          .then(d => fill(gSel, d.results));
    };

    /* 触发一次现有值的联动 */
    [pSel, cSel, semSel, slotSel].forEach(el => el.dispatchEvent(new Event('change')));
    console.log('[enroll v3] bindings done');
  }

  /* ---------- wait DOM ---------- */
  const wait = setInterval(() => {
    const els = ['id_parent', 'id_student', 'id_course', 'id_semester', 'id_course_slot', 'id_sub_group'].map($);
    if (els.every(Boolean)) { clearInterval(wait); bind(...els); }
  }, 80);
})();
