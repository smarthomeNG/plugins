// ----- widgets_openweathermap.rain_overview ----------------------------------------------------
$.widget("widgets_openweathermap.rain_overview", $.sv.widget, {
  initSelector: 'div[data-widget="widgets_openweathermap.rain_overview"]',

  options: {
    chartOptions: null,
  },

  _create: function () {
    this._super();

    var plots = Array();

    plots[0] = {
      type: "column",
      name: "Regen",
      lineWidth: 1,
    };

    var defaultOptions = {
      series: plots,
      chart: { styledMode: true },
      title: { text: "" },
      legend: { enabled: false },
      xAxis: {
        categories: [
          "00:00",
          "01:00",
          "02:00",
          "03:00",
          "04:00",
          "05:00",
          "06:00",
          "07:00",
          "08:00",
          "09:00",
          "10:00",
          "11:00",
          "12:00",
          "13:00",
          "14:00",
          "15:00",
          "16:00",
          "17:00",
          "18:00",
          "19:00",
          "20:00",
          "21:00",
          "22:00",
          "23:00",
        ],
        plotLines: [
          {
            color: "red", // Color value
            dashStyle: "solid", // Style of the plot line. Default to solid
            value: 12, // Value of where the line will appear
            width: 10, // Width of the line
          },
        ],
      },
      yAxis: { min: 0, max: 2, title: { text: "mm", x: 60, y: 20 } },
      navigation: {
        // options for export context menu
        buttonOptions: {
          enabled: false,
        },
      },
      plotOptions: {
        area: { enableMouseTracking: false },
      },
    };

    var userOptions = this.options.chartOptions;
    var allOptions = {};
    $.extend(true, allOptions, defaultOptions, userOptions);
    this.element.highcharts(allOptions);
  },

  _update: function (response) {
    var chart = this.element.highcharts();
    var today = new Date()
    if(response[2]) {
      today = new Date(response[2] * 1000);
    }
    today.setHours(today.getHours() - 12);
    for (i = 0; i < 24; i++) {
      newHours = today.getHours();
      chart.xAxis[0].categories[i] = newHours + ":00";
      today.setHours(today.getHours() + 1);
    }
    chart.series[0].setData(
      JSON.parse("[" + response[0] + ", " + response[1] + "]")
    );
    chart.redraw();
  },
});
