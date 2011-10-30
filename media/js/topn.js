var topNner = (function() {

    function plot(data) {
        // Format data for flot
        console.log(data);
        
        var lines = [];
        var artists = [];

        for (var i=0, len=data.length; i<len; i++) {
            var entry = data[i];
            artists.push(entry.artist);
            lines.push({ data: entry.data });
        }

        // And plot
        $.plot($("#topn"), lines, {
            lines: { show: true },
//            points: { show: true },
            grid:  { hoverable: true, borderWidth: 0 },
            xaxis: { ticks: false, panRange: [-10, 10] },
            yaxis: { ticks: false, panRange: [-10, 10] },
             zoom: { interactive: true }/*,
             pan: { interactive: true }*/
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