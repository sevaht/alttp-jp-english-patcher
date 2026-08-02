// Minimal headless libretro frontend: load core + ROM, run frames, dump PNGs.
// Usage: runner <core.so> <rom.sfc> <out_prefix> <total_frames> [every] [SCHED...]
//   SCHED tokens: startFrame-endFrame:BUTTON  (BUTTON: START SELECT A B X Y L R UP DOWN LEFT RIGHT)
//   e.g. 400-420:START 900-905:A  -> hold START frames 400..420, A frames 900..905
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <dlfcn.h>
#include "libretro.h"

static enum retro_pixel_format g_fmt = RETRO_PIXEL_FORMAT_0RGB1555;
static const void *g_fb; static unsigned g_w, g_h; static size_t g_pitch;
static int g_frame = 0;

#define MAXSCHED 64
static struct { int a, b, id; } g_sched[MAXSCHED]; static int g_nsched = 0;

static int btn_id(const char *n) {
    if(!strcmp(n,"B"))return RETRO_DEVICE_ID_JOYPAD_B;
    if(!strcmp(n,"Y"))return RETRO_DEVICE_ID_JOYPAD_Y;
    if(!strcmp(n,"SELECT"))return RETRO_DEVICE_ID_JOYPAD_SELECT;
    if(!strcmp(n,"START"))return RETRO_DEVICE_ID_JOYPAD_START;
    if(!strcmp(n,"UP"))return RETRO_DEVICE_ID_JOYPAD_UP;
    if(!strcmp(n,"DOWN"))return RETRO_DEVICE_ID_JOYPAD_DOWN;
    if(!strcmp(n,"LEFT"))return RETRO_DEVICE_ID_JOYPAD_LEFT;
    if(!strcmp(n,"RIGHT"))return RETRO_DEVICE_ID_JOYPAD_RIGHT;
    if(!strcmp(n,"A"))return RETRO_DEVICE_ID_JOYPAD_A;
    if(!strcmp(n,"X"))return RETRO_DEVICE_ID_JOYPAD_X;
    if(!strcmp(n,"L"))return RETRO_DEVICE_ID_JOYPAD_L;
    if(!strcmp(n,"R"))return RETRO_DEVICE_ID_JOYPAD_R;
    return -1;
}

static bool environ_cb(unsigned cmd, void *data) {
    switch (cmd) {
        case RETRO_ENVIRONMENT_SET_PIXEL_FORMAT: g_fmt = *(const enum retro_pixel_format*)data; return true;
        case RETRO_ENVIRONMENT_GET_CAN_DUPE: *(bool*)data = true; return true;
        case RETRO_ENVIRONMENT_GET_SYSTEM_DIRECTORY:
        case RETRO_ENVIRONMENT_GET_SAVE_DIRECTORY: *(const char**)data = "."; return true;
        case RETRO_ENVIRONMENT_GET_VARIABLE_UPDATE: *(bool*)data = false; return true;
        default: return false;
    }
}
static void video_cb(const void *data, unsigned w, unsigned h, size_t pitch) {
    if (data) { g_fb = data; g_w = w; g_h = h; g_pitch = pitch; }
}
static void input_poll_cb(void) {}
static int16_t input_state_cb(unsigned port, unsigned dev, unsigned idx, unsigned id) {
    if (port != 0) return 0;
    for (int i = 0; i < g_nsched; i++)
        if (g_sched[i].id == (int)id && g_frame >= g_sched[i].a && g_frame <= g_sched[i].b)
            return 1;
    return 0;
}
static void audio_cb(int16_t l, int16_t r) {}
static size_t audio_batch_cb(const int16_t *d, size_t f) { return f; }

static void dump_ppm(const char *path) {
    if (!g_fb) { fprintf(stderr, "no frame yet\n"); return; }
    FILE *f = fopen(path, "wb");
    fprintf(f, "P6\n%u %u\n255\n", g_w, g_h);
    for (unsigned y = 0; y < g_h; y++) {
        const uint8_t *row = (const uint8_t*)g_fb + y * g_pitch;
        for (unsigned x = 0; x < g_w; x++) {
            uint8_t r, g, b;
            if (g_fmt == RETRO_PIXEL_FORMAT_XRGB8888) {
                const uint32_t p = ((const uint32_t*)row)[x];
                r=(p>>16)&0xFF; g=(p>>8)&0xFF; b=p&0xFF;
            } else if (g_fmt == RETRO_PIXEL_FORMAT_RGB565) {
                const uint16_t p = ((const uint16_t*)row)[x];
                r=((p>>11)&0x1F)<<3; g=((p>>5)&0x3F)<<2; b=(p&0x1F)<<3;
            } else {
                const uint16_t p = ((const uint16_t*)row)[x];
                r=((p>>10)&0x1F)<<3; g=((p>>5)&0x1F)<<3; b=(p&0x1F)<<3;
            }
            fputc(r,f); fputc(g,f); fputc(b,f);
        }
    }
    fclose(f);
}

#define SYM(h,name) do{ *(void**)(&name)=dlsym(h,#name); if(!name){fprintf(stderr,"missing %s\n",#name);exit(1);} }while(0)

int main(int argc, char **argv) {
    if (argc < 5) { fprintf(stderr,"usage: %s core rom prefix frames [every] [a-b:BTN ...]\n",argv[0]); return 1; }
    const char *core=argv[1], *rom=argv[2], *prefix=argv[3];
    int frames=atoi(argv[4]); int every=argc>5?atoi(argv[5]):0;
    for (int i=6;i<argc && g_nsched<MAXSCHED;i++){
        char btn[16]; int a,b;
        if (sscanf(argv[i],"%d-%d:%15s",&a,&b,btn)==3){ int id=btn_id(btn);
            if(id>=0){ g_sched[g_nsched].a=a; g_sched[g_nsched].b=b; g_sched[g_nsched].id=id; g_nsched++;
                       fprintf(stderr,"sched: hold %s frames %d..%d\n",btn,a,b); } }
    }

    void *h = dlopen(core, RTLD_LAZY);
    if (!h) { fprintf(stderr,"dlopen: %s\n", dlerror()); return 1; }
    void (*retro_init)(void); void (*retro_deinit)(void);
    void (*set_environment)(retro_environment_t); void (*set_video_refresh)(retro_video_refresh_t);
    void (*set_input_poll)(retro_input_poll_t); void (*set_input_state)(retro_input_state_t);
    void (*set_audio_sample)(retro_audio_sample_t); void (*set_audio_sample_batch)(retro_audio_sample_batch_t);
    bool (*load_game)(const struct retro_game_info*); void (*run)(void);
    void (*get_av)(struct retro_system_av_info*);
    void* (*get_mem)(unsigned); size_t (*get_mem_sz)(unsigned);
    SYM(h,retro_init); SYM(h,retro_deinit);
    *(void**)&run=dlsym(h,"retro_run");
    *(void**)&load_game=dlsym(h,"retro_load_game");
    *(void**)&get_av=dlsym(h,"retro_get_system_av_info");
    *(void**)&get_mem=dlsym(h,"retro_get_memory_data");
    *(void**)&get_mem_sz=dlsym(h,"retro_get_memory_size");
    if(!run||!load_game||!get_av){fprintf(stderr,"missing core run/load/av\n");return 1;}
    *(void**)&set_environment=dlsym(h,"retro_set_environment");
    *(void**)&set_video_refresh=dlsym(h,"retro_set_video_refresh");
    *(void**)&set_input_poll=dlsym(h,"retro_set_input_poll");
    *(void**)&set_input_state=dlsym(h,"retro_set_input_state");
    *(void**)&set_audio_sample=dlsym(h,"retro_set_audio_sample");
    *(void**)&set_audio_sample_batch=dlsym(h,"retro_set_audio_sample_batch");

    set_environment(environ_cb); set_video_refresh(video_cb);
    set_input_poll(input_poll_cb); set_input_state(input_state_cb);
    set_audio_sample(audio_cb); set_audio_sample_batch(audio_batch_cb);
    retro_init();

    FILE *rf=fopen(rom,"rb"); if(!rf){perror("rom");return 1;}
    fseek(rf,0,SEEK_END); long sz=ftell(rf); fseek(rf,0,SEEK_SET);
    void *buf=malloc(sz); fread(buf,1,sz,rf); fclose(rf);
    struct retro_game_info gi = { .path=rom, .data=buf, .size=(size_t)sz, .meta=NULL };
    if (!load_game(&gi)) { fprintf(stderr,"load_game failed\n"); return 1; }

    // optional: load an SRM into SAVE_RAM (id 0) so we can resume a save file
    const char* srm = getenv("SRM");
    if (srm && get_mem && get_mem_sz) {
        void* sram = get_mem(0); size_t ssz = get_mem_sz(0);
        FILE* sf = fopen(srm, "rb");
        if (sf && sram && ssz) {
            size_t n = fread(sram, 1, ssz, sf); fclose(sf);
            fprintf(stderr, "loaded SRM: %zu bytes into save ram (%zu)\n", n, ssz);
        } else fprintf(stderr, "SRM load failed (sram=%p ssz=%zu)\n", sram, get_mem_sz(0));
    }

    struct retro_system_av_info av; get_av(&av);
    fprintf(stderr,"av: %ux%u fmt=%d\n", av.geometry.base_width, av.geometry.base_height, g_fmt);

    char path[512];
    for (int i=1;i<=frames;i++){
        g_frame=i; run();
        if (every && i%every==0){ snprintf(path,sizeof path,"%s_%04d.ppm",prefix,i); dump_ppm(path); }
    }
    snprintf(path,sizeof path,"%s_final.ppm",prefix); dump_ppm(path);
    // dump WRAM (RETRO_MEMORY_SYSTEM_RAM=2) for inspecting $7E/$7F buffers
    if (get_mem && get_mem_sz) {
        void* wram = get_mem(2); size_t wsz = get_mem_sz(2);
        if (wram && wsz) {
            snprintf(path,sizeof path,"%s_wram.bin",prefix);
            FILE* wf=fopen(path,"wb"); fwrite(wram,1,wsz,wf); fclose(wf);
            fprintf(stderr,"wram dumped: %zu bytes\n", wsz);
        }
        void* sr = get_mem(0); size_t srz = get_mem_sz(0);
        if (sr && srz) {
            snprintf(path,sizeof path,"%s_sram.bin",prefix);
            FILE* sf=fopen(path,"wb"); fwrite(sr,1,srz,sf); fclose(sf);
            fprintf(stderr,"sram dumped: %zu bytes\n", srz);
        }
        void* vr = get_mem(3); size_t vrz = get_mem_sz(3);
        if (vr && vrz) {
            snprintf(path,sizeof path,"%s_vram.bin",prefix);
            FILE* vf=fopen(path,"wb"); fwrite(vr,1,vrz,vf); fclose(vf);
            fprintf(stderr,"vram dumped: %zu bytes\n", vrz);
        } else fprintf(stderr,"no VRAM via id 3 (ptr=%p sz=%zu)\n", vr, vrz);
    }
    fprintf(stderr,"done %d frames\n", frames);
    return 0;
}
