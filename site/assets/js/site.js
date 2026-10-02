// Breaking Walls — small site script (no dependencies)
(function () {
  document.documentElement.classList.add("js");

  // Header: folder dropdown + mobile menu
  var burger = document.querySelector(".hd-burger");
  var mobile = document.querySelector(".hd-mobile");
  if (burger && mobile) {
    burger.addEventListener("click", function () {
      var open = burger.getAttribute("aria-expanded") === "true";
      burger.setAttribute("aria-expanded", String(!open));
      mobile.hidden = open;
      document.body.style.overflow = open ? "" : "hidden";
    });
  }
  document.querySelectorAll(".has-sub > button").forEach(function (b) {
    b.addEventListener("click", function () {
      var li = b.parentElement;
      var open = li.classList.toggle("open");
      b.setAttribute("aria-expanded", String(open));
    });
  });
  document.addEventListener("click", function (e) {
    document.querySelectorAll(".has-sub.open").forEach(function (li) {
      if (!li.contains(e.target)) { li.classList.remove("open"); li.firstElementChild.setAttribute("aria-expanded", "false"); }
    });
  });

  // Background videos: honour playback speed set in Squarespace
  document.querySelectorAll("video[data-rate]").forEach(function (v) {
    var r = parseFloat(v.dataset.rate) || 1;
    v.playbackRate = r;
    v.addEventListener("loadeddata", function () { v.playbackRate = r; });
  });

  // Bokeh generative backgrounds: sprinkle light particles
  document.querySelectorAll(".gen-bokeh").forEach(function (el) {
    for (var i = 0; i < 70; i++) {
      var d = document.createElement("i");
      var s = Math.random() * 3 + 1;
      d.style.width = d.style.height = s + "px";
      d.style.top = (35 + Math.random() * 25) + "%";
      d.style.left = (Math.random() * 200) + "%";
      d.style.opacity = (Math.random() * .7 + .2).toFixed(2);
      d.style.animationDuration = (60 + Math.random() * 80) + "s";
      d.style.animationDelay = (-Math.random() * 120) + "s";
      el.appendChild(d);
    }
  });

  // Galleries: reel + slideshow arrows
  document.querySelectorAll("[data-reel], [data-slides]").forEach(function (g) {
    var track = g.querySelector(".reel-track, .slides-track");
    var step = function (dir) {
      var w = g.hasAttribute("data-slides") ? track.clientWidth : track.clientWidth * 0.6;
      var max = track.scrollWidth - track.clientWidth;
      var next = track.scrollLeft + dir * w;
      if (next > max + 5) next = 0;
      if (next < -5) next = max;
      track.scrollTo({ left: next, behavior: "smooth" });
    };
    g.querySelector(".g-prev").addEventListener("click", function () { step(-1); });
    g.querySelector(".g-next").addEventListener("click", function () { step(1); });
  });

  // Fade-in on scroll
  var els = document.querySelectorAll(".fe-block, .cblk, .ui-card, .post-card, .gal-grid figure");
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add("is-in"); io.unobserve(en.target); } });
    }, { rootMargin: "0px 0px -5% 0px" });
    els.forEach(function (el) { io.observe(el); });
  } else {
    els.forEach(function (el) { el.classList.add("is-in"); });
  }

  // Language switcher dropdown
  document.querySelectorAll(".lang > button").forEach(function (b) {
    b.addEventListener("click", function (e) {
      e.stopPropagation();
      var open = b.parentElement.classList.toggle("open");
      b.setAttribute("aria-expanded", String(open));
    });
  });
  document.addEventListener("click", function () {
    document.querySelectorAll(".lang.open").forEach(function (l) { l.classList.remove("open"); l.firstElementChild.setAttribute("aria-expanded", "false"); });
  });

  // Contact form: posts to the endpoint set in FORM_ENDPOINT (see README). Falls back to email.
  var FORM_ENDPOINT = "";
  var FALLBACK_EMAIL = "info@breakingwalls.co";
  document.querySelectorAll("form[data-form-endpoint]").forEach(function (f) {
    f.addEventListener("submit", function (e) {
      e.preventDefault();
      var data = new FormData(f);
      if (!FORM_ENDPOINT) {
        var body = [];
        data.forEach(function (v, k) { body.push(k + ": " + v); });
        location.href = "mailto:" + FALLBACK_EMAIL + "?subject=" + encodeURIComponent(document.documentElement.lang.indexOf("fr") === 0 ? "Contact site web" : "Website contact") + "&body=" + encodeURIComponent(body.join("\n"));
        return;
      }
      fetch(FORM_ENDPOINT, { method: "POST", body: data, headers: { Accept: "application/json" } })
        .then(function (r) { if (!r.ok) throw r; f.querySelectorAll("label, button").forEach(function (x) { x.hidden = true; }); f.querySelector(".cform-ok").hidden = false; })
        .catch(function () { alert((document.documentElement.lang.indexOf("fr") === 0 ? "Désolé, le message n'a pas pu être envoyé. Écrivez-nous à " : "Sorry, the message could not be sent. Please email ") + FALLBACK_EMAIL); });
    });
  });
})();
