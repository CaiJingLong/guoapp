import 'package:duanju_app/local_store.dart';
import 'package:duanju_app/main.dart';
import 'package:flutter/material.dart';
import 'package:media_kit/media_kit.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:window_manager/window_manager.dart';

import '../test/macos_fixtures.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  if (!const bool.fromEnvironment('DISABLE_REMOTE_IMAGES')) {
    throw StateError('合成验证必须禁用站源图片');
  }
  MediaKit.ensureInitialized();
  await windowManager.ensureInitialized();
  await windowManager.setTitle('真果鉴 · macOS 合成验证');
  SharedPreferences.setMockInitialValues({});
  final store = LocalStore(await SharedPreferences.getInstance());
  final repository = MacosFixtureRepository();
  await repository.initialize();
  runApp(DuanjuApp(repository: repository, store: store));
}
