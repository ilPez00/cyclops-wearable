// CyclUno lean-HUD host gate: RAM budget, nav, notes ring, JSON in/out.
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "cycluno.h"

using namespace cycluno;

struct Capture : RowSink {
    char rows[ROWS][COLS + 2];
    Capture() { memset(rows, 0, sizeof(rows)); }
    void row(uint8_t idx, const char* text) override {
        if (idx < ROWS) { strncpy(rows[idx], text, COLS + 1); rows[idx][COLS + 1] = 0; }
    }
};

static uint8_t last_cmd = 0;
static void cmd_cb(uint8_t act) { last_cmd = act; }
static bool led_state = false;
static void led_cb(bool on) { led_state = on; }

int main() {
    // RAM budget: the whole point of the lean HUD. Uno has 2 KB total;
    // decoder(256B) + serial(64B) + stack must fit beside it.
    printf("sizeof(UnoHud)=%zu\n", sizeof(UnoHud));
    assert(sizeof(UnoHud) < 400);

    UnoHud h; h.send_cmd = cmd_cb; h.on_rec_led = led_cb; h.init();

    // HOME renders a ready banner + hints
    Capture c0; h.render(c0);
    assert(strstr(c0.rows[0], "HOME"));
    assert(strstr(c0.rows[1], "CyclUno ready"));
    assert(strstr(c0.rows[3], "A:rec"));
    printf("PASS home screen\n");

    // A on HOME toggles REC: cmd sent, led on, toast overlay
    h.on_btn_a();
    assert(last_cmd == ACT_TRANSCRIBE_START && led_state);
    assert(h.recording());
    Capture c1; h.render(c1);
    assert(strstr(c1.rows[0], "REC on"));   // toast wins row 0
    h.on_btn_a();
    assert(!h.recording() && !led_state);
    printf("PASS rec toggle + led + toast\n");

    // NOTE frames land as notes, newest first, ring capped
    h.apply_display_cmd("{\"text\":\"first note\"}");
    h.apply_display_cmd("{\"kind\":1,\"data\":\"second note\"}");
    assert(h.note_count() == 2);
    for (int i = 0; i < 6; ++i) {
        char buf[48]; snprintf(buf, sizeof(buf), "{\"text\":\"note %d\"}", i);
        h.apply_display_cmd(buf);
    }
    assert(h.note_count() == MAX_NOTES);   // capped
    Capture c2; h.render(c2);
    assert(strstr(c2.rows[1], "note 5"));  // newest is the HOME banner line
    printf("PASS notes ring (newest first, capped at %d)\n", MAX_NOTES);

    // garbage JSON must be ignored, not crash or add junk
    uint8_t before = h.note_count();
    h.apply_display_cmd("not json at all");
    h.apply_display_cmd("{\"text\":12}");
    assert(h.note_count() == before);
    printf("PASS garbage frames ignored\n");

    // B opens MENU; wheel moves selection; A on "Notes" enters NOTES
    for (int i = 0; i < 5; ++i) h.tick();  // let the REC toast expire first
    h.on_btn_b();
    Capture c3; h.render(c3);
    assert(strstr(c3.rows[0], "MENU") && c3.rows[1][0] == '>');
    h.on_wheel(1); h.on_wheel(-1);         // down and back up
    h.on_btn_a();                          // select "Notes"
    assert(h.mode() == UnoHud::NOTES);
    Capture c4; h.render(c4);
    assert(c4.rows[1][0] == '>');
    h.on_wheel(1);
    assert(h.note_sel() == 1);
    printf("PASS menu + wheel nav\n");

    // status JSON is clamped + parseable-shaped
    char st[24]; int n = h.status_json(st, sizeof(st));
    assert(n == (int)strlen(st) && n < (int)sizeof(st));
    char big[96]; n = h.status_json(big, sizeof(big));
    assert(big[n - 1] == '}');
    printf("PASS status_json clamped (%s)\n", big);

    // toast decays after its TTL ticks
    h.toast("hello");
    for (int i = 0; i < 5; ++i) h.tick();
    Capture c5; h.render(c5);
    assert(!strstr(c5.rows[0], "hello"));
    printf("PASS toast TTL decay\n");

    printf("ALL CYCLUNO TESTS PASSED\n");
    return 0;
}
