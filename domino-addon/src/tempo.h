// Turns Domino's MIDI clock (24 ticks per quarter note) into a tempo for FL Studio.
//
// Domino's clock wobbles by about 0.5 ms per tick (not adding up over time). A straight line fitted
// through the tick times gives the tick length; its uncertainty (3 sigma) is about +-0.4 BPM after one
// beat and +-0.05 after four. A whole BPM is preferred whenever it fits, otherwise the tempo is rounded
// to 0.1 BPM. After a change the tempo is fine-tuned until it fits over the whole window; from then on it
// only changes when the measurement no longer agrees with it within that uncertainty plus 0.1 BPM, or
// when a whole BPM fits better.
//
// When Domino jumps to another place while playing, its clock restarts at the new place, so one tick
// comes early (or a little late). Such a tick starts a new piece of the measurement; the line keeps one
// slope across all pieces, so the jump doesn't disturb the tempo.
#pragma once
#include <algorithm>
#include <cmath>
#include <deque>
#include <vector>

class TempoReader {
public:
    static constexpr double JITTER_S = 0.0006;   // wobble of Domino's clock (measured 0.52 ms standard deviation)
    static constexpr double STEP_S = 0.0025;     // a tick this much longer or shorter than usual is a jump
    static constexpr double OFF_S = 0.0016;      // a tick this far off the line through the ticks before it is a jump too
    static constexpr int WINDOW = 97;            // ticks measured over (4 beats)
    static constexpr double FULL_SXX = WINDOW * (double(WINDOW) * WINDOW - 1) / 12.0;

    TempoReader() { reset(); }

    void reset() {
        pieces_.assign(1, std::vector<double>());
        intervals_.clear();
        hasSent_ = false;
        settled_ = false;
    }

    // Feed the time of one clock tick (seconds). Returns true when FL should get a new tempo (bpm).
    bool feed(double now, double& bpm_out) {
        if (!pieces_.back().empty() && now - pieces_.back().back() > 0.25)
            reset();                                  // clock stopped in between: Domino stopped and started again
        if (!pieces_.back().empty() && jumped(pieces_.back(), now))
            pieces_.emplace_back();                   // Domino jumped to another place: start a new piece
        pieces_.back().push_back(now);
        size_t total = 0;
        for (auto& p : pieces_) total += p.size();
        while (total > WINDOW) {                      // measure over the last 4 beats
            pieces_.front().erase(pieces_.front().begin());
            total--;
            if (pieces_.front().empty()) pieces_.erase(pieces_.begin());
        }
        if ((long)total - (long)pieces_.size() < 24)  // intervals inside the pieces
            return false;
        // least-squares slope of tick time over tick number, one slope for all pieces
        double sxx = 0, sxy = 0;
        for (auto& p : pieces_) {
            double a, b, mi, mt;
            fit(p, a, b, mi, mt);
            sxx += a;
            sxy += b;
        }
        double tick = sxy / sxx;
        const std::vector<double>& piece = pieces_.back();
        if (piece.size() >= 13 && std::fabs((piece[piece.size() - 1] - piece[piece.size() - 13]) / 12 - tick) > 0.03 * tick) {
            std::vector<double> keep(piece.end() - 13, piece.end());   // the tempo changed: measure again
            pieces_.assign(1, keep);
            return false;
        }
        double bpm = 60.0 / (tick * 24);
        double uncertainty = 3 * bpm * JITTER_S / std::sqrt(sxx) / tick;
        double whole = std::round(bpm);
        double value = std::fabs(bpm - whole) <= uncertainty ? whole : std::round(bpm * 10) / 10;
        if (hasSent_) {
            double off = std::fabs(bpm - lastSent_);
            if (value == lastSent_ || off <= uncertainty) {
                if (sxx >= 0.8 * FULL_SXX) settled_ = true;    // fits over (nearly) the whole window
                return false;                                  // the tempo FL has still fits
            }
            if (off <= uncertainty + 0.1 && value != whole && settled_)
                return false;                                  // close enough, and no whole BPM to offer
        }
        lastSent_ = value;
        hasSent_ = true;
        settled_ = false;
        bpm_out = value;
        return true;
    }

private:
    static void fit(const std::vector<double>& p, double& sxx, double& sxy, double& mean_i, double& mean_t) {
        size_t m = p.size();
        mean_i = (m - 1) / 2.0;
        mean_t = 0;
        for (double x : p) mean_t += x;
        mean_t /= m;
        sxx = m * (double(m) * m - 1) / 12.0;
        sxy = 0;
        for (size_t i = 0; i < m; i++) sxy += (i - mean_i) * (p[i] - mean_t);
    }

    bool jumped(const std::vector<double>& piece, double now) {
        double interval = now - piece.back();
        bool have_usual = intervals_.size() >= 3;
        double usual = 0;
        if (have_usual) {
            std::vector<double> s(intervals_.begin(), intervals_.end());
            std::sort(s.begin(), s.end());
            usual = s[s.size() / 2];
        }
        intervals_.push_back(interval);
        if (intervals_.size() > 5) intervals_.pop_front();
        if (have_usual && std::fabs(interval - usual) > STEP_S) return true;
        if (piece.size() >= 24) {                       // smaller jumps: compare with the line through this piece
            double sxx, sxy, mean_i, mean_t;
            fit(piece, sxx, sxy, mean_i, mean_t);
            return std::fabs(now - (mean_t + sxy / sxx * (piece.size() - mean_i))) > OFF_S;
        }
        return false;
    }

    std::vector<std::vector<double>> pieces_;   // tick times, split where the clock jumped
    std::deque<double> intervals_;
    double lastSent_ = 0;
    bool hasSent_ = false;
    bool settled_ = false;
};
