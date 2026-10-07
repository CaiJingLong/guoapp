package core

import (
	"bytes"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestNativePlaybackMP4IgnoresPlaylistWordsInSignedURL(t *testing.T) {
	body := append([]byte("\x00\x00\x00\x1cftypisom"), bytes.Repeat([]byte{0x42}, 4<<20)...)
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "video/mp4")
		_, _ = w.Write(body)
	}))
	defer upstream.Close()
	engine, err := newNativeEngine(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	stream, err := newNativeStreamServer(engine.downloader)
	if err != nil {
		t.Fatal(err)
	}
	defer stream.server.Close()
	for _, suffix := range []string{"/video/?rc=signaturehLSvalue", "/video/?hint=m3u8", "/hls-cache/video.mp4"} {
		t.Run(suffix, func(t *testing.T) {
			address, token := stream.nativeOpen(providerMedia{URL: upstream.URL + suffix, CENCKey: bytes.Repeat([]byte{1}, 16)})
			defer stream.nativeRelease(token)
			if !strings.HasSuffix(address, ".mp4") {
				t.Errorf("MP4 classified as a playlist: %s", address)
			}
			response, err := http.Get(address)
			if err != nil {
				t.Fatal(err)
			}
			defer response.Body.Close()
			actual, err := io.ReadAll(response.Body)
			if err != nil {
				t.Fatal(err)
			}
			if response.StatusCode != http.StatusOK || !bytes.Equal(actual, body) {
				t.Fatalf("MP4 was not streamed intact: status=%d, bytes=%d", response.StatusCode, len(actual))
			}
		})
	}
}
