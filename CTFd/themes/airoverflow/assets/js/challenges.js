import Alpine from "alpinejs";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";

dayjs.extend(relativeTime);

import CTFd from "./index";

import { Modal, Tab, Tooltip } from "bootstrap";
import highlight from "./theme/highlight";
import { embed } from "./utils/graphs/echarts";

function addTargetBlank(html) {
  let dom = new DOMParser();
  let view = dom.parseFromString(html, "text/html");
  let links = view.querySelectorAll('a[href*="://"]');
  links.forEach(link => {
    link.setAttribute("target", "_blank");
  });
  return view.documentElement.outerHTML;
}

window.Alpine = Alpine;

Alpine.store("challenge", {
  data: {
    view: "",
    solves: [],
  },
});

Alpine.data("Hint", () => ({
  id: null,
  html: null,

  async showHint(event) {
    if (event.target.open) {
      let response = await CTFd.pages.challenge.loadHint(this.id);

      // Hint has some kind of prerequisite or access prevention
      if (response.errors) {
        event.target.open = false;
        CTFd._functions.challenge.displayUnlockError(response);
        return;
      }
      let hint = response.data;
      if (hint.content) {
        this.html = addTargetBlank(hint.html);
      } else {
        let answer = await CTFd.pages.challenge.displayUnlock(this.id);
        if (answer) {
          let unlock = await CTFd.pages.challenge.loadUnlock(this.id);

          if (unlock.success) {
            let response = await CTFd.pages.challenge.loadHint(this.id);
            let hint = response.data;
            this.html = addTargetBlank(hint.html);
          } else {
            event.target.open = false;
            CTFd._functions.challenge.displayUnlockError(unlock);
          }
        } else {
          event.target.open = false;
        }
      }
    }
  },
}));

Alpine.data("Challenge", () => ({
  id: null,
  next_id: null,
  submission: "",
  tab: null,
  solves: [],
  submissions: [],
  solution: null,
  response: null,
  share_url: null,
  max_attempts: 0,
  attempts: 0,
  ratingValue: 0,
  selectedRating: 0,
  ratingReview: "",
  ratingSubmitted: false,

  async init() {
    highlight();
  },

  getStyles() {
    return {};
  },

  async showChallenge() {
    // No-op for tabs
  },

  async showSolves() {
    this.solves = Alpine.store("challenge").data.solves || [];
  },

  async showSubmissions() {
    let response = await CTFd.pages.users.userSubmissions("me", this.id);
    this.submissions = response.data;
    this.submissions.forEach(s => {
      s.date = dayjs(s.date).format("MMMM Do, h:mm:ss A");
      return s;
    });
    new Tab(this.$el).show();
  },

  getSolutionId() {
    let data = Alpine.store("challenge").data;
    return data.solution_id;
  },

  getSolutionState() {
    let data = Alpine.store("challenge").data;
    return data.solution_state;
  },

  setSolutionId(solutionId) {
    Alpine.store("challenge").data.solution_id = solutionId;
  },

  async showSolution() {
    let solution_id = this.getSolutionId();
    CTFd._functions.challenge.displaySolution = solution => {
      this.solution = solution.html;
      new Tab(this.$el).show();
    };
    await CTFd.pages.challenge.displaySolution(solution_id);
  },

  getNextId() {
    let data = Alpine.store("challenge").data;
    return data.next_id;
  },

  async nextChallenge() {
    let modal = Modal.getOrCreateInstance("[x-ref='challengeWindow']");

    // TODO: Get rid of this private attribute access
    // See https://github.com/twbs/bootstrap/issues/31266
    modal._element.addEventListener(
      "hidden.bs.modal",
      event => {
        // Dispatch load-challenge event to call loadChallenge in the ChallengeBoard
        Alpine.nextTick(() => {
          this.$dispatch("load-challenge", this.getNextId());
        });
      },
      { once: true },
    );
    modal.hide();
  },

  async getShareUrl() {
    let body = {
      type: "solve",
      challenge_id: this.id,
    };
    const response = await CTFd.fetch("/api/v1/shares", {
      method: "POST",
      body: JSON.stringify(body),
    });
    const data = await response.json();
    const url = data["data"]["url"];
    this.share_url = url;
  },

  copyShareUrl() {
    navigator.clipboard.writeText(this.share_url);
    let t = Tooltip.getOrCreateInstance(this.$el);
    t.enable();
    t.show();
    setTimeout(() => {
      t.hide();
      t.disable();
    }, 2000);
  },

  async submitChallenge() {
    this.response = await CTFd.pages.challenge.submitChallenge(
      this.id,
      this.submission,
    );

    await this.renderSubmissionResponse();
  },

  async renderSubmissionResponse() {
    if (this.response.data.status === "correct") {
      this.submission = "";
    }

    // Decide whether to check for the solution
    if (this.getSolutionId() == null) {
      if (
        CTFd.pages.challenge.checkSolution(
          this.getSolutionState(),
          Alpine.store("challenge").data,
          this.response.data.status,
        )
      ) {
        let data = await CTFd.pages.challenge.getSolution(this.id);
        this.setSolutionId(data.id);
      }
    }

    // Increment attempts counter
    if (
      this.max_attempts > 0 &&
      this.response.data.status != "already_solved" &&
      this.response.data.status != "ratelimited"
    ) {
      this.attempts += 1;
    }

    // Dispatch load-challenges event to call loadChallenges in the ChallengeBoard
    this.$dispatch("load-challenges");
  },

  async submitRating() {
    const response = await CTFd.pages.challenge.submitRating(
      this.id,
      this.selectedRating,
      this.ratingReview,
    );
    if (response.value) {
      this.ratingValue = this.selectedRating;
      this.ratingSubmitted = true;
    } else {
      alert("Error submitting rating");
    }
  },
}));

Alpine.data("ChallengeBoard", () => ({
  loaded: false,
  challenges: [],
  challenge: null,
  view: "list",
  searchQuery: "",
  currentChallengeId: null,
  recentSolves: [],

  async init() {
    this.challenges = await CTFd.pages.challenges.getChallenges();
    this.loaded = true;

    if (window.location.hash) {
      this.handleHash();
    }
  },

  handleHash() {
    let hash = window.location.hash;
    if (!hash) {
      this.view = "list";
      return;
    }
    let chalHash = decodeURIComponent(hash.substring(1));
    let idx = chalHash.lastIndexOf("-");
    if (idx >= 0) {
      let id = chalHash.slice(idx + 1);
      if (id && id !== "null") {
        this.loadChallenge(id, false);
      }
    } else {
      this.view = "list";
    }
  },

  handlePopState(event) {
    this.handleHash();
  },

  getCategories() {
    const categories = [];

    this.challenges.forEach(challenge => {
      const { category } = challenge;

      if (!categories.includes(category)) {
        categories.push(category);
      }
    });

    try {
      const f = CTFd.config.themeSettings.challenge_category_order;
      if (f) {
        const getSort = new Function(`return (${f})`);
        categories.sort(getSort());
      }
    } catch (error) {
      // Ignore errors with theme category sorting
      console.log("Error running challenge_category_order function");
      console.log(error);
    }

    return categories;
  },

  getChallenges(category) {
    let challenges = this.challenges;

    if (category !== null) {
      challenges = challenges.filter(challenge => challenge.category === category);
    }

    if (this.searchQuery) {
      challenges = challenges.filter(challenge => {
        return (
          challenge.name.toLowerCase().includes(this.searchQuery.toLowerCase()) ||
          challenge.category.toLowerCase().includes(this.searchQuery.toLowerCase())
        );
      });
    }

    try {
      const f = CTFd.config.themeSettings.challenge_order;
      if (f) {
        const getSort = new Function(`return (${f})`);
        challenges.sort(getSort());
      }
    } catch (error) {
      // Ignore errors with theme challenge sorting
      console.log("Error running challenge_order function");
      console.log(error);
    }

    return challenges;
  },

  async loadChallenges() {
    this.challenges = await CTFd.pages.challenges.getChallenges();
  },

  async loadChallenge(challengeId, pushState = true) {
    if (!challengeId || challengeId === "null") return;
    this.currentChallengeId = challengeId;
    this.recentSolves = [];

    // Fetch solves concurrently for the sidebar
    CTFd.pages.challenge.loadSolves(challengeId).then(solves => {
      if (Array.isArray(solves)) {
        solves.forEach(s => {
          s.date = dayjs(s.date).fromNow();
        });
        this.recentSolves = solves;
        Alpine.store("challenge").data.solves = solves;
      }
    });

    this.renderGraph(challengeId);

    await CTFd.pages.challenge.displayChallenge(challengeId, challenge => {
      challenge.data.view = addTargetBlank(challenge.data.view);
      challenge.data.solves = this.recentSolves;
      Alpine.store("challenge").data = challenge.data;

      Alpine.nextTick(() => {
        this.view = "detail";
        if (pushState) {
          history.pushState(null, null, `#${challenge.data.name}-${challengeId}`);
        }
      });
    });
  },

  async renderGraph(challengeId) {
    try {
      const response = await CTFd.fetch(`/api/v1/challenges/${challengeId}/statistics`);
      if (!response.ok) {
        console.log("Statistics endpoint not available for this challenge.");
        return;
      }
      const stats = await response.json();
      const data = stats.data;

      // Arena-style area chart
      const option = {
        grid: {
          left: "5%",
          right: "5%",
          top: "10%",
          bottom: "10%",
          containLabel: true,
        },
        tooltip: {
          trigger: "axis",
          backgroundColor: "rgba(10, 10, 15, 0.9)",
          borderColor: "rgba(255, 255, 255, 0.1)",
          textStyle: { color: "#fff" }
        },
        xAxis: {
          type: "category",
          boundaryGap: false,
          data: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
          axisLine: { show: false },
          axisLabel: { color: "rgba(255,255,255,0.4)", fontSize: 10 }
        },
        yAxis: {
          type: "value",
          splitLine: { lineStyle: { color: "rgba(255,255,255,0.05)", type: "dashed" } },
          axisLabel: { color: "rgba(255,255,255,0.4)", fontSize: 10 }
        },
        series: [
          {
            name: "Attempts",
            type: "line",
            smooth: true,
            symbolSize: 0,
            lineStyle: { color: "rgba(255,255,255,0.2)", width: 2 },
            areaStyle: { color: "rgba(255,255,255,0.05)" },
            data: [data.wrong || 0, (data.wrong || 0) + (data.solve || 0), data.wrong || 0, 15, 10, 20, 15]
          },
          {
            name: "Solves",
            type: "line",
            smooth: true,
            symbolSize: 6,
            itemStyle: { color: "#10b981" },
            lineStyle: { width: 3 },
            areaStyle: {
              color: {
                type: 'linear',
                x: 0, y: 0, x2: 0, y2: 1,
                colorStops: [{ offset: 0, color: 'rgba(16,185,129,0.3)' }, { offset: 1, color: 'rgba(16,185,129,0)' }]
              }
            },
            data: [0, 2, 5, 3, data.solve || 0, 7, 10]
          }
        ]
      };

      const target = document.getElementById("solve-graph");
      if (target) {
        embed(target, option);
      }
    } catch (e) {
      console.log("Error rendering graph:", e);
    }
  },

  async refreshChallenge() {
    if (this.currentChallengeId) {
      await this.loadChallenge(this.currentChallengeId, false);
    }
  },

  goBack() {
    this.view = "list";
    this.currentChallengeId = null;
    history.pushState(null, null, window.location.pathname + window.location.search);
  },
}));

Alpine.start();
