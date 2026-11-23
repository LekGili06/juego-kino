/* Pantalla del iPad de mamá. Solo ES5: debe funcionar en Safari 9 (iPad 2, iOS 9). */
(function () {
  'use strict';

  var CLAVE = location.pathname.split('/')[2] || '';
  var CADA_CONFIG = 60 * 1000;          // revisar si hay pregunta
  var CADA_LATIDO = 5 * 60 * 1000;      // avisar que el iPad está vivo
  var CADA_VOZ = 5 * 60 * 1000;         // repetir la pregunta en voz alta
  var CADA_REINTENTO = 30 * 1000;       // reintentar envíos fallidos
  var MAX_LADO = 640;
  var DIAS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
  var MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
    'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];

  var config = null;
  var respondida = leer('respondida');   // pregunta (ISO) ya contestada en este iPad
  var ultimoId = null;                   // id de la última respuesta, para la foto
  var temporizadorVoz = null;
  var temporizadorGracias = null;

  // --- utilidades -------------------------------------------------------

  function $(id) { return document.getElementById(id); }

  function leer(k) {
    try { return window.localStorage.getItem(k); } catch (e) { return null; }
  }

  function guardar(k, v) {
    try {
      if (v === null) { window.localStorage.removeItem(k); } else { window.localStorage.setItem(k, v); }
    } catch (e) { /* modo privado: seguimos sin guardar */ }
  }

  function dos(n) { return (n < 10 ? '0' : '') + n; }

  function horaDeIso(iso) { return iso ? iso.substr(11, 5) : ''; }

  function conexion(ok) { $('punto').style.display = ok ? 'none' : 'block'; }

  function api(metodo, ruta, cuerpo, tipo, alTerminar) {
    var xhr = new XMLHttpRequest();
    var sep = ruta.indexOf('?') === -1 ? '?' : '&';
    xhr.open(metodo, '/api/' + ruta + sep + 'clave=' + encodeURIComponent(CLAVE), true);
    if (tipo) { xhr.setRequestHeader('Content-Type', tipo); }
    xhr.timeout = 20000;
    xhr.onreadystatechange = function () {
      if (xhr.readyState !== 4) { return; }
      var ok = xhr.status === 200;
      var datos = null;
      if (ok) {
        try { datos = JSON.parse(xhr.responseText); } catch (e) { ok = false; }
      }
      conexion(ok || (xhr.status >= 400 && xhr.status < 500));
      if (alTerminar) { alTerminar(ok, datos, xhr.status); }
    };
    xhr.send(cuerpo || null);
  }

  // --- pantallas --------------------------------------------------------

  function mostrar(id) {
    var ps = document.querySelectorAll('.pantalla');
    for (var i = 0; i < ps.length; i++) {
      ps[i].className = ps[i].id === id ? 'pantalla visible' : 'pantalla';
    }
    if (id !== 'pregunta' && temporizadorVoz) {
      clearInterval(temporizadorVoz);
      temporizadorVoz = null;
    }
  }

  function visible() {
    var v = document.querySelector('.pantalla.visible');
    return v ? v.id : '';
  }

  function actualizarReloj() {
    var d = new Date();
    $('hora').innerHTML = dos(d.getHours()) + ':' + dos(d.getMinutes());
    $('fecha').innerHTML = DIAS[d.getDay()] + ' ' + d.getDate() + ' de ' + MESES[d.getMonth()];
  }

  function gracias() {
    mostrar('gracias');
    if (temporizadorGracias) { clearTimeout(temporizadorGracias); }
    temporizadorGracias = setTimeout(function () {
      if (visible() === 'gracias') { mostrar('reposo'); }
    }, 5000);
  }

  // --- voz ----------------------------------------------------------------

  function vozEspanol() {
    if (!window.speechSynthesis || !window.speechSynthesis.getVoices) { return null; }
    var voces = window.speechSynthesis.getVoices();
    var preferidas = ['es-CL', 'es-US', 'es-MX', 'es-ES'];
    for (var p = 0; p < preferidas.length; p++) {
      for (var i = 0; i < voces.length; i++) {
        if (voces[i].lang && voces[i].lang.replace('_', '-') === preferidas[p]) { return voces[i]; }
      }
    }
    for (var j = 0; j < voces.length; j++) {
      if (voces[j].lang && voces[j].lang.indexOf('es') === 0) { return voces[j]; }
    }
    return null;
  }

  function hablar(texto) {
    if (!window.speechSynthesis || !window.SpeechSynthesisUtterance) { return; }
    try {
      var u = new SpeechSynthesisUtterance(texto);
      var voz = vozEspanol();
      u.lang = voz ? voz.lang : 'es-ES';
      if (voz) { u.voice = voz; }
      u.rate = 0.9;
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(u);
    } catch (e) { /* sin voz: la pregunta igual está en pantalla */ }
  }

  // --- preguntas ----------------------------------------------------------

  function preguntar() {
    mostrar('pregunta');
    hablar('Hola. ¿Cómo te sientes?');
    temporizadorVoz = setInterval(function () { hablar('¿Cómo te sientes?'); }, CADA_VOZ);
  }

  function aplicarConfig(datos) {
    config = datos;
    $('proxima').innerHTML = 'Próxima pregunta: ' + horaDeIso(datos.proxima);
    var hay = datos.pendiente && datos.pendiente !== respondida;
    var v = visible();
    if (hay && v === 'reposo') { preguntar(); }
    if (!hay && v === 'pregunta') { mostrar('reposo'); }
  }

  function cargarConfig() {
    api('GET', 'config', null, null, function (ok, datos) {
      if (ok) { aplicarConfig(datos); }
    });
  }

  function latido() { api('POST', 'latido', null, null, null); }

  function enviarPendiente() {
    var pendiente = leer('envioPendiente');
    if (!pendiente) { return; }
    api('POST', 'respuesta', pendiente, 'application/json', function (ok, datos, status) {
      if (ok || (status >= 400 && status < 500)) { guardar('envioPendiente', null); }
      if (ok) { ultimoId = datos.id; }
    });
  }

  function responder(estado) {
    respondida = config && config.pendiente ? config.pendiente : null;
    guardar('respondida', respondida);
    guardar('envioPendiente', JSON.stringify({ estado: estado }));
    ultimoId = null;
    mostrar('enviando');
    $('enviando').getElementsByTagName('h1')[0].innerHTML = 'Un momento…';
    api('POST', 'respuesta', leer('envioPendiente'), 'application/json', function (ok, datos, status) {
      if (ok || (status >= 400 && status < 500)) { guardar('envioPendiente', null); }
      if (ok) {
        ultimoId = datos.id;
        mostrar('foto');
      } else {
        gracias();  // se reintenta en segundo plano; sin respuesta guardada no hay foto
      }
    });
  }

  // --- foto ---------------------------------------------------------------

  function dataUrlABlob(dataUrl) {
    var partes = dataUrl.split(',');
    var binario = atob(partes[1]);
    var bytes = new Uint8Array(binario.length);
    for (var i = 0; i < binario.length; i++) { bytes[i] = binario.charCodeAt(i); }
    return new Blob([bytes], { type: 'image/jpeg' });
  }

  function reducirYEnviar(archivo) {
    var lector = new FileReader();
    lector.onload = function () {
      var img = new Image();
      img.onload = function () {
        var escala = Math.min(1, MAX_LADO / Math.max(img.width, img.height));
        var lienzo = document.createElement('canvas');
        lienzo.width = Math.round(img.width * escala);
        lienzo.height = Math.round(img.height * escala);
        lienzo.getContext('2d').drawImage(img, 0, 0, lienzo.width, lienzo.height);
        var datos = new FormData();
        datos.append('foto', dataUrlABlob(lienzo.toDataURL('image/jpeg', 0.7)), 'foto.jpg');
        api('POST', 'foto?id=' + ultimoId, datos, null, function () { gracias(); });
      };
      img.onerror = function () { gracias(); };
      img.src = lector.result;
    };
    lector.onerror = function () { gracias(); };
    lector.readAsDataURL(archivo);
  }

  // --- arranque -----------------------------------------------------------

  function empezar() {
    hablar(' ');  // iOS exige un toque antes de permitir la voz
    mostrar('reposo');
    actualizarReloj();
    cargarConfig();
    latido();
    enviarPendiente();
    setInterval(actualizarReloj, 10 * 1000);
    setInterval(cargarConfig, CADA_CONFIG);
    setInterval(latido, CADA_LATIDO);
    setInterval(enviarPendiente, CADA_REINTENTO);
  }

  $('b-empezar').onclick = empezar;

  var botones = document.querySelectorAll('#pregunta button');
  for (var i = 0; i < botones.length; i++) {
    botones[i].onclick = function () { responder(this.getAttribute('data-estado')); };
  }

  $('b-no-foto').onclick = gracias;

  $('archivo').onchange = function () {
    var archivo = this.files && this.files[0];
    if (!archivo || !ultimoId) { gracias(); return; }
    mostrar('enviando');
    $('enviando').getElementsByTagName('h1')[0].innerHTML = 'Enviando foto…';
    reducirYEnviar(archivo);
  };
})();
