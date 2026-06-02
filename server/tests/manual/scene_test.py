if __name__ == "__main__":
    from vcal.scene import Scene2

    scene = Scene2()
    scene.save()
    scene.prepare_for_alarm()
    input("Press Enter to restore after alarm...")
    scene.restore_after_alarm()