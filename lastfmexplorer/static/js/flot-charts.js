define([
    "jquery", "dates", "jquery.flot"
], function ($, Dates) {
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

    function cumulative_average() {
        var current_average = 0,
            num_points = 0,
            averages = [];
        return {
            // Cumulative average:
            // CA_i+1 = CA_i + ((x_i+1 - CA_i) / i+1)
            // where CA_i = last average,
            //      x_i+1 = new entry's value.
            "update": function (timestamp, value) {
                num_points += 1;
                current_average = current_average + ((value - current_average) / num_points);
                averages.push([timestamp, current_average]);
            },
            "get": function() {
                return averages;
            }
        }
    }
    
    /** Expects weeklies to be a list of (week index, playcount, [average]) tuples */
    function weekly_line(target, weeklies, config) {
        var config = config || {},
            start = config.start,
            end = config.end,
            show_averages = config.show_averages || false;

        var weekly_data = [],
            averager = cumulative_average(),
            last_week = ((start === undefined) ? weeklies[0][0] : start) - 1;

        for (var i=0, len=weeklies.length; i<len; ++i) {
            var week      = weeklies[i][0],
                playcount = weeklies[i][1],
                timestamp = Dates.timestamp_of_week(week);

            // fill in missing weeks at beginning or in the middle
            while (last_week != week-1) {
                last_week += 1;
                var missing_timestamp = Dates.timestamp_of_week(last_week);
                weekly_data.push([missing_timestamp, 0]);
                if (show_averages) {
                    averager.update(missing_timestamp, 0);
                }
            }

            weekly_data.push([timestamp, playcount]);
            if (show_averages) {
                averager.update(timestamp, playcount);
            }
            last_week = week;
        }

        // fill in missing weeks at end
        if (end !== undefined) {
            while (last_week != end) {
                last_week += 1;
                timestamp = Dates.timestamp_of_week(last_week);
                weekly_data.push([timestamp, 0]);
                if (show_averages) {
                    averager.update(timestamp, 0)
                }
            }
        }
        var charts = [{data: weekly_data, color: "#00f"}];
        if (show_averages) {
            charts.push({data: averager.get(), color: "#007f02"});
        }
        plot_line_chart(target, charts);
    }

    return {
        "monthly_counts": monthly_counts,
        "weekly_hist": weekly_hist,
        "weekly_line": weekly_line
    }
});
