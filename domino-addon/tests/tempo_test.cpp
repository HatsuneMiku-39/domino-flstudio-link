// Feeds clock tick times (seconds, one per line) through the add-on's TempoReader and prints every tempo
// it would send to FL Studio:  tempo_test.exe ticks.txt
// tools\export_ticks.py makes such files from recordings and simulations, so the C++ version can be
// compared with the Python one it was ported from.
#include <stdio.h>
#include "../src/tempo.h"

int main(int argc, char** argv) {
    if (argc < 2) return 2;
    FILE* f = nullptr;
    if (fopen_s(&f, argv[1], "r") || !f) return 1;
    TempoReader reader;
    double t, first = -1, bpm;
    int sends = 0;
    while (fscanf_s(f, "%lf", &t) == 1) {
        if (first < 0) first = t;
        if (reader.feed(t, bpm)) {
            printf("%s(%.2f, %g)", sends++ ? ", " : "", t - first, bpm);
        }
    }
    printf("\n%d sends\n", sends);
    fclose(f);
    return 0;
}
