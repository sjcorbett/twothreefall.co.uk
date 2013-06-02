requirejs.config({
    baseUrl: '/static/js',
    paths:{
        "jquery": "vendor/jquery",
        "excanvas": "vendor/excanvas",
        "jquery.flot": "vendor/jquery.flot",
        "moment": "vendor/moment"
    },
    "shim": {
        "excanvas": ["jquery"],
        "jquery.flot": ["jquery"]
    }
});
