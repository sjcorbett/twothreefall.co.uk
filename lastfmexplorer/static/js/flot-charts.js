define([
    "jquery", "vendor/jquery.flot"
], function ($) {
    function plot_line_chart(divid, data) {
        $.plot($(divid), data, {
            lines: { show: true },
            xaxis: { mode: "time", timeformat: "%b %y" },
            grid: { hoverable: true }
        });

        bindTooltip(divid);
    }

    // Showing tooltips.
    function bindTooltip(element) {

        function showTooltip(x, y, contents) {
            $('<div id="tooltip">' + contents + '</div>').css({
                position: 'absolute',
                display: 'none',
                top: y - 20,
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

    function monthly_counts(target, data) {
        var monthly_data = [];
        var month_ticks = [];
        var months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

        for (var i=0, len=data.length; i<len; ++i) {
            monthly_data.push([i, data[i]]);
            month_ticks.push([i, months[i]]);
        }

        $.plot($(target), [{data : monthly_data, color: "#00f"}], {
            bars:  { show: true, barWidth: 0.75, fill: 0.8, align: "center" },
            xaxis: { ticks: month_ticks },
            grid:  { hoverable: true, borderWidth: 0 }
        });
        bindTooltip(target);
    }

    function weekly_hist(target, step, counts) {
        var weekly_data = [];
        var weekly_ticks = [];
        for (var i=0, len=counts.length; i<len; ++i) {
            weekly_data.push([i, counts[i]]);
            weekly_ticks.push([i, ((step*i) + ((i == 0) ? 0 : 1)) + "-" + (step*(i+1))]);

        }
        $.plot($(target), [{data : weekly_data, color: "#00f"}], {
            bars:  { show: true, barWidth: 0.75, fill: 0.8, align: "center" },
            xaxis: { ticks: weekly_ticks },
            grid:  { hoverable: true, borderWidth: 0 }
        });
        bindTooltip(target);
    }

    function weekly_line(target, weeklies) {
        var weekly_data = [];
        var averages = [];

        for (var i=0, len=weeklies.length; i<len; ++i) {
            weekly_data.push([weeklies[i][0], weeklies[i][1]]);
            averages.push([weeklies[i][0], weeklies[i][2]]);
        }
        plot_line_chart(target, [
            {data : weekly_data, color: "#00f"},
            {data: averages, color: "#007f02"}
        ]);
    }

    return {
        "monthly_counts": monthly_counts,
        "weekly_hist": weekly_hist,
        "weekly_line": weekly_line
    }
});
