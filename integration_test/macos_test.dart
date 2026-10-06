import 'dart:io';

import 'package:duanju_app/local_store.dart';
import 'package:duanju_app/main.dart';
import 'package:duanju_app/media_library.dart';
import 'package:duanju_app/media_pipeline.dart';
import 'package:duanju_app/player_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:ffmpeg_kit_flutter_new_min_gpl/ffmpeg_kit_config.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:media_kit/media_kit.dart';
import 'package:media_kit_video/media_kit_video.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:window_manager/window_manager.dart';

import '../test/macos_fixtures.dart';

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets(
    'macOS native core, MP4, encrypted HLS, CENC, fullscreen and FFmpeg',
    (tester) async {
      expect(Platform.isMacOS, isTrue);
      expect(const bool.fromEnvironment('DISABLE_REMOTE_IMAGES'), isTrue);
      MediaKit.ensureInitialized();
      await windowManager.ensureInitialized();
      SharedPreferences.setMockInitialValues({});
      final store = LocalStore(await SharedPreferences.getInstance());
      final repository = MacosFixtureRepository();
      FFmpegKitConfig.enableLogCallback((log) {
        if (log.getLevel() >= 0 && log.getLevel() <= 16) {
          debugPrintSynchronously('FFmpeg fixture: ${log.getMessage()}');
        }
      });
      await repository.initialize();
      final detail = await repository.detail(MacosFixtureRepository.drama);
      final evidence = <Map<String, Object?>>[];

      Future<void> until(bool Function() ready, String step) async {
        final watch = Stopwatch()..start();
        while (!ready()) {
          if (watch.elapsed > const Duration(seconds: 40)) {
            fail('Timed out: $step');
          }
          await tester.pump(const Duration(milliseconds: 200));
        }
      }

      await tester.pumpWidget(DuanjuApp(repository: repository, store: store));
      await until(
        () =>
            find.text(MacosFixtureRepository.drama.title).evaluate().isNotEmpty,
        'catalog',
      );
      await tester.tap(find.text(MacosFixtureRepository.drama.title).first);
      await until(
        () => find.byType(Video).evaluate().isNotEmpty,
        'open player',
      );
      var player = tester
          .widget<Video>(find.byType(Video).first)
          .controller
          .player;
      await player.setVolume(0);

      for (var index = 0; index < 3; index++) {
        if (index > 0) {
          await tester.pumpWidget(const SizedBox.shrink());
          await tester.pump(const Duration(milliseconds: 500));
          await tester.pumpWidget(
            MaterialApp(
              home: PlayerScreen(
                detail: detail,
                initialIndex: index,
                repository: repository,
                store: store,
              ),
            ),
          );
          await until(
            () => find.byType(Video).evaluate().isNotEmpty,
            'video $index',
          );
          player = tester
              .widget<Video>(find.byType(Video).first)
              .controller
              .player;
          await player.setVolume(0);
        }
        await until(
          () =>
              (player.state.width ?? 0) > 0 &&
              player.state.position.inMilliseconds > 500,
          'decode ${index + 1}',
        );
        evidence.add({
          'episode': index + 1,
          'width': player.state.width,
          'height': player.state.height,
          'positionMs': player.state.position.inMilliseconds,
        });
        await player.seek(const Duration(seconds: 5));
        await until(
          () => player.state.position.inSeconds >= 5,
          'seek ${index + 1}',
        );
        expect(tester.takeException(), isNull);
      }
      await tester.tap(find.byTooltip('旋转与全屏').first);
      await tester.pump(const Duration(seconds: 2));
      expect(await windowManager.isFullScreen(), isTrue);
      await windowManager.setFullScreen(false);
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump(const Duration(seconds: 1));

      final directory = await Directory.systemTemp.createTemp(
        'guoapp-macos-media-',
      );
      final client = HttpClient();
      final library = MediaLibrary(repository, store);
      try {
        final input = File('${directory.path}/fixture.mp4');
        final response = await (await client.getUrl(
          Uri.parse('$macosFixtureBase/clear.mp4'),
        )).close();
        await response.pipe(input.openWrite());
        final executor = FFmpegExecutor();
        verifyMediaDuration(await executor.probe(input.path), 20);
        final output = '${directory.path}/remuxed.mkv';
        await executor.run(['-i', input.path, '-c', 'copy', output]);
        verifyMediaDuration(await executor.probe(output), 20);
        final concat = File('${directory.path}/concat.txt');
        await concat.writeAsString(
          '${concatFileLine(input.path)}\n${concatFileLine(input.path)}\n',
        );
        final merged = '${directory.path}/merged.mp4';
        await executor.run([
          '-f',
          'concat',
          '-safe',
          '0',
          '-i',
          concat.path,
          '-c',
          'copy',
          merged,
        ]);
        verifyMediaDuration(await executor.probe(merged), 40);

        await repository.enqueueDownloads(
          detail,
          detail.episodes.take(2).toList(),
        );
        final downloadWatch = Stopwatch()..start();
        while (true) {
          final jobs = (await repository.downloads())
              .where((job) => job.drama.id == MacosFixtureRepository.drama.id)
              .toList();
          expect(
            jobs.where((job) => job.state == 'failed').map((job) => job.error),
            isEmpty,
          );
          if (jobs.length == 2 && jobs.every((job) => job.completed)) break;
          if (downloadWatch.elapsed > const Duration(seconds: 40)) {
            fail('Timed out: downloads');
          }
          await tester.pump(const Duration(milliseconds: 200));
        }
        for (final episode in detail.episodes.take(2)) {
          final local = await repository.localPlayback(detail.drama, episode);
          expect(local?.local, isTrue);
        }
        await library.exportJobs(
          (await repository.downloads())
              .where((job) => job.drama.id == MacosFixtureRepository.drama.id)
              .toList(),
        );
        final exported = library.items
            .where((item) => item.drama.id == MacosFixtureRepository.drama.id)
            .toList();
        expect(exported, hasLength(2));
        for (final item in exported) {
          verifyMediaDuration(await executor.probe(library.fileFor(item)), 20);
        }
        binding.reportData = {
          'macos': {
            'playback': evidence,
            'seek': true,
            'fullscreen': true,
            'ffprobe': true,
            'remux': true,
            'merge': true,
            'mp4AndHlsDownloads': true,
            'offlineExport': true,
            'remoteImagesDisabled': true,
          },
        };
      } finally {
        client.close(force: true);
        for (final item
            in library.items
                .where(
                  (item) => item.drama.id == MacosFixtureRepository.drama.id,
                )
                .toList()) {
          await library.remove(item);
        }
        library.dispose();
        for (final job in (await repository.downloads()).where(
          (job) => job.drama.id == MacosFixtureRepository.drama.id,
        )) {
          await repository.controlDownloads('remove', id: job.id);
        }
        await directory.delete(recursive: true);
        store.dispose();
      }
    },
    timeout: const Timeout(Duration(minutes: 5)),
  );
}
