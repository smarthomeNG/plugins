function rtr_timer(ts) {

    if (ts === "") {
        return "";
    } else {
        d = new Date(ts*1000);;
        return "Timer endet " + d.transUnit("H:i, d.m.");
    }
}
