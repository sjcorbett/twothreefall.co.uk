requirejs.config({
    baseUrl: '/static/js',
    paths:{
        "jquery": "vendor/jquery"
    },
    "shim": {
        "vendor/excanvas": ["vendor/jquery"],
        "vendor/jquery.flot": ["jquery"]
    }
});
