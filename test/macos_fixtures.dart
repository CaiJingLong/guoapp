import 'package:duanju_app/core_bridge.dart';
import 'package:duanju_app/models.dart';

const macosFixtureBase = String.fromEnvironment(
  'FIXTURE_BASE_URL',
  defaultValue: 'http://127.0.0.1:38473',
);

class MacosFixtureRepository extends NativeRepository {
  static const drama = Drama(
    id: 'hongguo:700073',
    source: 'hongguo',
    title: 'macOS 合成媒体验证',
    episodes: 3,
    category: 'MP4 · AES HLS · CENC',
  );

  @override
  bool get supportsSourceManagement => false;

  @override
  Future<CatalogPage> catalog(
    String source, {
    int page = 1,
    String query = '',
    String category = '',
    bool force = false,
  }) async =>
      CatalogPage(query.isEmpty || drama.title.contains(query) ? [drama] : []);

  @override
  Future<CatalogPage> cached(String source, {String category = ''}) async =>
      CatalogPage([drama]);

  @override
  Future<List<CatalogCategory>> categories(
    String source, {
    bool force = false,
  }) async => const [CatalogCategory.all];

  @override
  Future<List<String>> suggestions(String query) async => [];

  @override
  Future<Drama?> supplementMetadata(Drama drama) async => drama;

  @override
  Future<String> cover(Drama drama, {bool force = false}) async => '';

  @override
  Future<DramaDetail> detail(Drama drama) async => DramaDetail(drama, [
    for (final entry in ['clear.mp4', 'index.m3u8', 'encrypted.mp4'].indexed)
      Episode({
        'id': '${entry.$1 + 1}',
        'source': 'hongguo',
        'currentEpisode': entry.$1 + 1,
        'title': ['普通 MP4', 'AES 加密 HLS', 'CENC 加密 MP4'][entry.$1],
        'videoUrl': '$macosFixtureBase/${entry.$2}',
        'referer': '$macosFixtureBase/',
      }, entry.$1 + 1),
  ]);

  @override
  Future<PlaybackPlan> resolve(
    Drama drama,
    Episode episode, {
    int quality = 0,
  }) async {
    final plan = await super.resolve(drama, episode, quality: quality);
    return episode.number == 3
        ? PlaybackPlan(
            url: plan.url,
            local: plan.local,
            headers: plan.headers,
            decryptionKey: '00112233445566778899aabbccddeeff',
            session: plan.session,
          )
        : plan;
  }

  @override
  Future<PlaybackPlan> resolveOnline(
    Drama drama,
    Episode episode, {
    int quality = 0,
  }) => resolve(drama, episode, quality: quality);

  @override
  Future<PlaybackPlan?> preload(
    Drama drama,
    Episode episode, {
    int quality = 0,
    bool online = false,
  }) async => null;
}
