function pollUpdate(user) {
    $.post(
        '/lastfmexplorer/poll-update', 
        { username : user },
        function(data) {
            console.log(data);
        }
    );
}

$(document).ready(function() {
    $("#start").submit(function() {
        return false;
    });
});
