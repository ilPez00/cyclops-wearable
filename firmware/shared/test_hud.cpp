// Host logic test for cyclops::Hud (no display hardware needed).
#include "hud.h"
#include "screen.h"
#include "ring_proto.h"
#include <cstdio>
#include <cstring>
#include <cassert>
#include <cctype>

using namespace cyclops;

// Fake screen: records draw calls, enforces geometry like a 128x32 (4 rows x 21 cols).
struct FakeScreen : Screen {
    int rows_=4, cols_=21;
    int draws=0; char last[64]=""; char row0[64]="";
    int w() const override { return 128; }
    int h() const override { return 32; }
    int char_cols() const override { return cols_; }
    int text_rows() const override { return rows_; }
    void begin() override {}
    void clear() override {}
    void set_ink(bool) override {}
    void draw_text(int, int row, const char* s) override { draws++; strncpy(last, s, 63); last[63]=0; if (row==0) { strncpy(row0, s, 63); row0[63]=0; } }
    void draw_rect(int,int,int,int,bool) override {}
    void flush() override {}
};

// Line-capturing screen: records every drawn line (for wrap/step assertions).
struct LineScreen : Screen {
    int rows_=21, cols_=21;
    char line[24][40]; int n=0;
    int w() const override { return 128; }
    int h() const override { return 128; }
    int char_cols() const override { return cols_; }
    int text_rows() const override { return rows_; }
    void begin() override {}
    void clear() override { n=0; }
    void set_ink(bool) override {}
    void draw_text(int, int, const char* s) override { if (n<24){ strncpy(line[n++], s, 39); line[n-1][39]=0; } }
    void draw_rect(int,int,int,int,bool) override {}
    void flush() override {}
};

static int cmds[32]; static int ncmd=0; static char carg[256];
static void on_cmd(uint8_t a, const char* arg) { if (ncmd<32){cmds[ncmd++]=a;} strncat(carg, arg, 255); }
static char agent_prompt[128]; static bool agent_called=false;
static void on_agent(const char* p) { agent_called=true; strncpy(agent_prompt, p?p:"", 127); agent_prompt[127]=0; }

int main() {
    Hud h; h.send_cmd = on_cmd; h.on_agent_request = on_agent; h.init();
    FakeScreen scr;
    h.render(scr);  // HOME

    h.on_select();          // HOME -> MENU
    assert(h.top() == MENU);
    h.menu_sel = 4;         // Health (menu: 0 Notes,1 Agent,2 Transcribe,3 Translate,4 Health)
    h.on_select();          // MENU -> HEALTH (no cmd)
    assert(h.top() == HEALTH);
    h.on_long_back();       // HEALTH -> MENU
    assert(h.top() == MENU);
    h.menu_sel = 0; h.on_select();  // -> NOTES
    assert(h.top() == NOTES);
    h.add_note("buy milk tomorrow");
    h.add_note("call marco about g2");
    h.add_note("ship the firmware");
    h.note_sel = 1; h.on_select();  // NOTES -> NOTE_DETAIL
    assert(h.top() == NOTE_DETAIL);
    assert(strcmp(h.detail, "call marco about g2") == 0);

    // Translate flow (index 3)
    h.home(); h.on_select(); h.menu_sel = 3; h.on_select();  // TRANSLATE
    assert(h.top() == TRANSLATE);
    assert(ncmd>0 && cmds[ncmd-1] == ACT_TRANSLATE);

    // Agent flow (index 1) — ask + streamed answer + glanceable banner
    h.home(); h.on_select(); h.menu_sel = 1; h.on_select();
    assert(h.top() == AGENT);
    h.agent_ask("what is 2+2?");
    assert(agent_called && strcmp(agent_prompt, "what is 2+2?") == 0);
    assert(h.top() == AGENT);
    h.append_agent("The answer is 4.");
    h.set_hud("The answer is 4.");
    assert(h.hud_len > 0);
    h.on_long_back();  // leaves AGENT -> sends ABORT
    assert(ncmd>0 && cmds[ncmd-1] == ACT_AGENT_ABORT);

    // Teleprompter paging (index 6)
    h.set_detail("line one\nline two\nline three\nline four\nline five");
    h.home(); h.on_select(); h.menu_sel = 6; h.on_select();
    assert(h.top() == TELEPROMPTER);
    h.on_wheel(1); assert(h.tele_page == 1);

    // Camera (7) + image analysis (8) + SSH (9) commands
    h.home(); h.on_select(); h.menu_sel = 7; h.on_select();
    assert(ncmd>0 && cmds[ncmd-1] == ACT_CAMERA);
    h.home(); h.on_select(); h.menu_sel = 8; h.on_select();
    assert(ncmd>0 && cmds[ncmd-1] == ACT_IMAGE_ANALYSIS);
    h.home(); h.on_select(); h.menu_sel = 9; h.on_select();
    assert(ncmd>0 && cmds[ncmd-1] == ACT_SSH);

    // Confirm flow
    h.request_confirm("store note?", ACT_CONFIRM_YES);
    assert(h.top() == CONFIRM);
    h.on_select();  // yes
    assert(h.top() != CONFIRM);
    assert(ncmd>0 && cmds[ncmd-1] == ACT_CONFIRM_YES);

    // Recording toggle via nod shows a timer
    bool r0 = h.recording; h.on_nod(); assert(h.recording != r0);
    h.tick_sec(); h.tick_sec();
    assert(h.rec_secs == 2);

    // Toast transient behaviour
    h.toast("sent", 1); assert(h.toast_ttl == 1);
    h.tick_sec(); assert(h.toast_ttl == 0);

    // Detail scroll on a long note (now supports AGENT too)
    h.home(); h.on_select(); h.menu_sel=0; h.on_select();
    h.add_note("a very long note that should scroll when we push wheel because it exceeds the visible width of the tiny screen by a lot");
    h.note_sel = h.note_count-1; h.on_select();
    int so0 = h.scroll_off; h.on_wheel(1); assert(h.scroll_off > so0);

    // Status bar renders a mode breadcrumb + flags (no crash on tiny screen)
    Hud h2; h2.send_cmd = on_cmd; h2.init();
    h2.recording = true; h2.bt = true; h2.hr = 72; h2.bead_batt = 15;
    FakeScreen scr2; h2.render(scr2);
 assert(strstr(scr2.row0, "REC") != nullptr);   // recording flag in status bar
 assert(strstr(scr2.row0, "BT") != nullptr);    // bluetooth flag
 assert(strstr(scr2.row0, "HOME") != nullptr || strstr(scr2.row0, "HLTH") != nullptr);

 // ---- consent gate: recording blocked when consent is off ----
 {
     Hud hc; hc.send_cmd = on_cmd; hc.init();
     hc.set_consent(false);
     hc.home(); hc.on_select(); hc.menu_sel = 2; hc.on_select(); // Transcribe
     assert(!hc.recording);                 // blocked, no REC
     hc.on_nod();                           // quick capture toggle
     assert(!hc.recording);                 // still blocked
     hc.set_consent(true);
     hc.on_nod();
     assert(hc.recording);                  // now allowed
     // consent JSON frame from brain toggles state
     Hud hc2; hc2.send_cmd = on_cmd; hc2.init();
     hc2.apply_display_cmd("{\"kind\":\"consent\",\"on\":0}");
     assert(!hc2.consent);
     hc2.apply_display_cmd("{\"kind\":\"consent\",\"on\":1}");
     assert(hc2.consent);
 }

 // ---- word-aware wrap: no mid-word split on a long agent answer ----
 {
     Hud hw; hw.send_cmd = on_cmd; hw.init();
     const char* big = "the quick brown fox jumps over the lazy dog while the agent streams a very long answer that must not split words mid token";
     hw.set_detail(big);
     hw.push(AGENT);
     LineScreen ls; hw.render(ls);
     // every captured line (except status row 0) must not split an alpha word
     for (int i = 1; i < ls.n; ++i) {
         const char* L = ls.line[i];
         // find a space followed by a letter at end-of-line case: a line ending
         // in a letter with next line starting with a letter => split. Reject.
         int len = (int)strlen(L);
         if (len > 0 && isalpha((unsigned char)L[len-1])) {
             // next line must not start with alpha (would be a split)
             if (i+1 < ls.n && isalpha((unsigned char)ls.line[i+1][0])) {
                 assert(!"word split across lines");
             }
         }
     }
 }

 // ---- agent progress bar + step ticks render on wide panels ----
 {
     Hud hp; hp.send_cmd = on_cmd; hp.init();
     hp.push(AGENT); hp.set_detail("thinking...");
     hp.set_progress(50); hp.add_step("device"); hp.add_step("web");
     LineScreen ls; hp.render(ls);
     bool bar = false, steps = false;
     for (int i = 0; i < ls.n; ++i) {
         if (strchr(ls.line[i], '[') && strchr(ls.line[i], ']')) bar = true;
         if (strstr(ls.line[i], "device")) steps = true;
     }
     assert(bar);   // progress bar present
     assert(steps); // step ticks present
 }

 // ---- idle auto-sleep after sleep_after seconds ----
 {
     Hud hs; hs.send_cmd = on_cmd; hs.init();
     hs.sleep_after = 3;
     hs.on_wheel(1); assert(hs.screen_on);  // input wakes
     for (int i = 0; i < 3; ++i) hs.tick_sec();
     assert(!hs.screen_on);                 // slept
     hs.on_wheel(1); assert(hs.screen_on);  // input wakes again
 }

 // ---- nav arrow maps heading to a compass glyph ----
 {
     Hud hn; hn.send_cmd = on_cmd; hn.init();
     hn.set_nav(120, 0, "home");
     hn.push(NAV);
     LineScreen ls; hn.render(ls);
     bool arrow = false;
     for (int i = 0; i < ls.n; ++i)
         if (strchr(ls.line[i], 0x18)) arrow = true;  // '↑' for north
     assert(arrow);
 }

 // ---- cancel (BTN_B): confirm-no in CONFIRM, else back one level ----
 {
     Hud hc; hc.send_cmd = on_cmd; hc.init();
     int before = ncmd;
     hc.request_confirm("store note?", ACT_CONFIRM_YES);
     assert(hc.top() == CONFIRM);
     hc.on_cancel();                       // declines
     assert(hc.top() != CONFIRM);
     assert(cmds[ncmd-1] == ACT_CONFIRM_NO);
     // back-out from a sub view
     hc.home(); hc.on_select(); hc.menu_sel = 0; hc.on_select(); // NOTES
     assert(hc.top() == NOTES);
     hc.on_cancel();
     assert(hc.top() == MENU);
     (void)before;
 }

 // ---- DISPLAY_CMD parse: progress/step/default route into Hud state ----
 {
     Hud hd; hd.send_cmd = on_cmd; hd.init();
     hd.push(AGENT);
     hd.apply_display_cmd("{\"kind\":\"progress\",\"p\":42}");
     assert(hd.progress == 42);
     hd.apply_display_cmd("{\"kind\":\"step\",\"tool\":\"device\"}");
     assert(hd.step_n == 1 && strcmp(hd.steps[0], "device") == 0);
     hd.apply_display_cmd("{\"kind\":\"step\",\"tool\":\"web\"}");
     assert(hd.step_n == 2 && strcmp(hd.steps[1], "web") == 0);
     // default text line -> note
     hd.apply_display_cmd("{\"kind\":\"text\",\"text\":\"hello world\"}");
     assert(hd.note_count == 1 && strcmp(hd.notes[0], "hello world") == 0);
 }

 // ---- COLMI R02 16-byte packet protocol (parser shared with Python) ----
{
    // battery response: cmd 3, level 64%, charging 0
    uint8_t batt[16] = {3, 64, 0, 0,0,0,0,0,0,0,0,0,0,0,0, 0};
    batt[15] = ring_checksum(batt);
    assert(ring_is_valid(batt));
    RingSample rs;
    assert(ring_parse(batt, rs));
    assert(rs.battery == 64 && !rs.charging);

    // real-time HR: cmd 105, kind=1 (HR), err=0, value=78
    uint8_t hr[16] = {105, 1, 0, 78, 0,0,0,0,0,0,0,0,0,0,0, 0};
    hr[15] = ring_checksum(hr);
    assert(ring_parse(hr, rs) && rs.hr == 78);

    // real-time SpO2: cmd 105, kind=3, value=97
    uint8_t sp[16] = {105, 3, 0, 97, 0,0,0,0,0,0,0,0,0,0,0, 0};
    sp[15] = ring_checksum(sp);
    assert(ring_parse(sp, rs) && rs.spo2 == 97);

    // error response (byte[0] >= 0x80) must be rejected
    uint8_t err[16] = {0x80|3, 0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0};
    err[15] = ring_checksum(err);
    assert(!ring_is_valid(err));
    RingSample rs2;
    assert(!ring_parse(err, rs2));  // ignored, no field change

    // bad checksum must be rejected
    uint8_t bad[16] = {3, 50, 0,0,0,0,0,0,0,0,0,0,0,0,0, 0};
    bad[15] = (uint8_t)(ring_checksum(bad) ^ 0xFF);  // corrupt CRC
    assert(!ring_is_valid(bad));

    // request builder round-trips checksum
    uint8_t req[16];
    ring_make_packet(req, RING_CMD_BATTERY);
    assert(req[0] == RING_CMD_BATTERY && req[15] == ring_checksum(req));
    uint8_t rt_req[16];
    uint8_t sub[2] = {RING_RT_HEART_RATE, 1};
    ring_make_packet(rt_req, RING_CMD_START_REAL_TIME, sub, 2);
    assert(rt_req[0] == RING_CMD_START_REAL_TIME && rt_req[1] == 1 && rt_req[2] == 1);
    assert(rt_req[15] == ring_checksum(rt_req));
}

printf("ALL HUD LOGIC TESTS PASSED (%d cmds issued)\n", ncmd);
    return 0;
}
