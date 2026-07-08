// Host logic test for cyclops::Hud (no display hardware needed).
#include "hud.h"
#include "screen.h"
#include <cstdio>
#include <cstring>
#include <cassert>

using namespace cyclops;

// Fake screen: records draw calls, enforces geometry like a 128x32 (4 rows x 21 cols).
struct FakeScreen : Screen {
    int rows_=4, cols_=21;
    int draws=0; char last[64]="";
    int w() const override { return 128; }
    int h() const override { return 32; }
    int char_cols() const override { return cols_; }
    int text_rows() const override { return rows_; }
    void begin() override {}
    void clear() override {}
    void set_ink(bool) override {}
    void draw_text(int, int, const char* s) override { draws++; strncpy(last, s, 63); last[63]=0; }
    void draw_rect(int,int,int,int,bool) override {}
    void flush() override {}
};

static int cmds[32]; static int ncmd=0; static char carg[256];
static void on_cmd(uint8_t a, const char* arg) { if (ncmd<32){cmds[ncmd++]=a;} strncat(carg, arg, 255); }

int main() {
    Hud h; h.send_cmd = on_cmd; h.init();
    FakeScreen scr;
    h.render(scr);  // HOME

    h.on_select();          // HOME -> MENU
    assert(h.top() == MENU);
    h.on_wheel(3);          // move to "Health"
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

    // Translate flow
    h.home(); h.on_select(); h.menu_sel = 2; h.on_select();  // TRANSLATE
    assert(h.top() == TRANSLATE);
    assert(ncmd>0 && cmds[ncmd-1] == ACT_TRANSLATE);

    // Teleprompter paging
    h.set_detail("line one\nline two\nline three\nline four\nline five");
    h.home(); h.on_select(); h.menu_sel = 5; h.on_select();
    assert(h.top() == TELEPROMPTER);
    h.on_wheel(1); assert(h.tele_page == 1);

    // Camera + image analysis commands
    h.home(); h.on_select(); h.menu_sel = 6; h.on_select();
    assert(ncmd>0 && cmds[ncmd-1] == ACT_CAMERA);
    h.home(); h.on_select(); h.menu_sel = 7; h.on_select();
    assert(ncmd>0 && cmds[ncmd-1] == ACT_IMAGE_ANALYSIS);
    h.home(); h.on_select(); h.menu_sel = 8; h.on_select();
    assert(ncmd>0 && cmds[ncmd-1] == ACT_SSH);

    // Confirm flow
    h.request_confirm("store note?", ACT_CONFIRM_YES);
    assert(h.top() == CONFIRM);
    h.on_select();  // yes
    assert(h.top() != CONFIRM);
    assert(ncmd>0 && cmds[ncmd-1] == ACT_CONFIRM_YES);

    // Recording toggle via nod
    bool r0 = h.recording; h.on_nod(); assert(h.recording != r0);

    // Detail scroll on a long note
    h.home(); h.on_select(); h.menu_sel=0; h.on_select();
    h.add_note("a very long note that should scroll when we push wheel because it exceeds the visible width of the tiny screen by a lot");
    h.note_sel = h.note_count-1; h.on_select();
    int so0 = h.scroll_off; h.on_wheel(1); assert(h.scroll_off > so0);

    printf("ALL HUD LOGIC TESTS PASSED (%d cmds issued)\n", ncmd);
    return 0;
}
