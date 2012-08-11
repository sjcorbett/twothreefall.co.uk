var topNner = (function() {

    function plot(data) {
        // Format data for flot
        var lines = [];
        var artists = [];

        // Line colours
        var palette = ["#000000",  // black
                       "#ff0000",  // red
                       "#007f02",  // green
                       "#0000ff",  // blue;
                       "#abcdef",  // light blue
                       "#333399", "#ff998b" ];
        var plength = palette.length;

        for (var i=0, len=data.length; i<len; i++) {
            var entry = data[i];
            artists.push(entry.artist);
            lines.push({
                data: entry.data,
                color: palette[i%plength],
                shadowSize: 0,
                xaxis: 2
            });
        }

        var xaxisvals = { mode: "time", timeformat: "%b %y", panRange: [0, lines[0].length] };

        // And plot
        $.plot($("#topn"), lines, {
            lines: { show: true, linewidth: 1 },
            grid:  { hoverable: true, borderWidth: 0 },
            xaxis: xaxisvals,
            x2axis: xaxisvals,
            yaxis: { ticks: false, panRange: [0, lines.length] },
            zoom: { interactive: true },
            pan: { interactive: true }
        });

        $("#topn").bind("plothover", function (event, pos, item) {
            if (item) {
                $("#hovered").html(artists[item.seriesIndex]);
            } else {
                $("#hovered").html("..hover");
            }
        });

        bindTooltip("#topn");
    }

    return { plot: plot };
})();