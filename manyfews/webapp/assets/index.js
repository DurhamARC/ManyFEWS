var dataUrl = '/depths';

window.addEventListener("map:init", function (e) {
  var detail = e.detail;
  fetch(dataUrl)
    .then(function(resp) {
      return resp.json();
    })
    .then(function(data) {
      console.log(data);
      data["items"].forEach(i => {
        L.rectangle(i.bounds, {
          color: null,
          fillColor: 'CornflowerBlue',
          fillOpacity: i.depth * 0.5,
        }).addTo(detail.map);
      });
    });
  }, false
);
