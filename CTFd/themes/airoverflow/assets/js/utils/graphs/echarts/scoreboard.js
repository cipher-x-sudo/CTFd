import { colorHash } from "@ctfdio/ctfd-js/ui";
import { mergeObjects } from "../../objects";
import { cumulativeSum } from "../../math";
import dayjs from "dayjs";

export function getOption(mode, places, optionMerge) {
  let option = {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(10, 10, 15, 0.9)",
      borderColor: "rgba(255, 255, 255, 0.1)",
      textStyle: {
        color: "#fff",
        fontFamily: "Inter, sans-serif",
      },
      axisPointer: {
        type: "cross",
        lineStyle: {
          color: "rgba(255, 255, 255, 0.2)",
          width: 1,
        },
      },
    },
    legend: {
      type: "scroll",
      orient: "horizontal",
      align: "left",
      bottom: 0,
      icon: "circle",
      textStyle: {
        color: "rgba(255, 255, 255, 0.8)",
        fontFamily: "Inter, sans-serif",
        fontSize: 12,
      },
      itemGap: 24,
      itemWidth: 10,
      itemHeight: 10,
      data: [],
    },
    toolbox: {
      show: true,
      feature: {
        saveAsImage: {
          title: "Save",
          iconStyle: {
            borderColor: "rgba(255, 255, 255, 0.5)",
          },
        },
      },
      right: 20,
      top: 0,
    },
    grid: {
      left: "3%",
      right: "5%",
      bottom: "12%",
      top: "8%",
      containLabel: true,
    },
    xAxis: [
      {
        type: "time",
        boundaryGap: false,
        axisLine: {
          show: false,
        },
        splitLine: {
          show: true,
          lineStyle: {
            color: "rgba(255, 255, 255, 0.05)",
            type: "dashed",
          },
        },
        axisLabel: {
          color: "rgba(255, 255, 255, 0.4)",
          fontSize: 11,
          margin: 15,
        },
        axisTick: {
          show: false,
        }
      },
    ],
    yAxis: [
      {
        type: "value",
        axisLine: {
          show: false,
        },
        splitLine: {
          show: true,
          lineStyle: {
            color: "rgba(255, 255, 255, 0.05)",
            type: "dashed",
          },
        },
        axisLabel: {
          color: "rgba(255, 255, 255, 0.4)",
          fontSize: 11,
          formatter: (value) => value.toLocaleString(),
          margin: 15,
        },
      },
    ],
    series: [],
  };

  const teams = Object.keys(places);
  for (let i = 0; i < teams.length; i++) {
    const team_score = [];
    const times = [];
    for (let j = 0; j < places[teams[i]]["solves"].length; j++) {
      team_score.push(places[teams[i]]["solves"][j].value);
      const date = dayjs(places[teams[i]]["solves"][j].date);
      times.push(date.toDate());
    }

    const total_scores = cumulativeSum(team_score);
    let scores = times.map(function (e, i) {
      return [e, total_scores[i]];
    });

    option.legend.data.push(places[teams[i]]["name"]);

    const data = {
      name: places[teams[i]]["name"],
      type: "line",
      smooth: false,
      symbol: "circle",
      symbolSize: 6,
      showSymbol: true,
      lineStyle: {
        width: 1.5,
        shadowBlur: 4,
        shadowColor: colorHash(places[teams[i]]["name"] + places[teams[i]]["id"]),
      },
      areaStyle: {
        opacity: 0.1,
        color: colorHash(places[teams[i]]["name"] + places[teams[i]]["id"]),
      },
      itemStyle: {
        color: colorHash(places[teams[i]]["name"] + places[teams[i]]["id"]),
      },
      data: scores,
    };
    option.series.push(data);
  }

  if (optionMerge) {
    option = mergeObjects(option, optionMerge);
  }
  return option;
}
