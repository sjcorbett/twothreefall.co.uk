define([
    "moment"
], function(moment) {

    var Dates = {};

    var the_beginning = moment(new Date(2005, 1, 20)).utc();

    Dates.date_of_week = function (week_index) {
        return the_beginning.clone().add('weeks', week_index);
    };

    Dates.timestamp_of_week = function (week_index) {
        return Dates.date_of_week(week_index).valueOf();
    };

    return Dates;
});
