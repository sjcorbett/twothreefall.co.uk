function plot_line_chart(divid, data) {
    $.plot($(divid), data, {
        lines: { show: true },
        xaxis: { mode: "time", timeformat: "%b %y" },
        grid:  { hoverable: true }
    });

    bindTooltip(divid);
}

// Showing tooltips.
function bindTooltip(element) {
    
    function showTooltip(x, y, contents) {
        $('<div id="tooltip">' + contents + '</div>').css( {
            position: 'absolute',
            display: 'none',
            top: y-20,
            left: x,
            border: '1px solid #fdd',
            padding: '2px',
            'background-color': '#ccc',
            opacity: 0.80
        }).appendTo("body").fadeIn(200);
    }

    var pY = null;
    $(element).bind("plothover", function (event, pos, item) {
        if (item) {
            var y = item.datapoint[1].toFixed(2);
            if (pY != y) {
                pY = y;
                $("#tooltip").remove();
                showTooltip(item.pageX, pos.pageY, Math.floor(y));
            }
        }
        else {
            pY = null;
            $("#tooltip").fadeOut(200);
        }
    });
}
