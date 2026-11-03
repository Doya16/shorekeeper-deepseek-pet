"""Offline verification of the real packaged update controls and reminder card."""
from datetime import date
from types import SimpleNamespace
from PySide6.QtWidgets import QApplication
from .paths import ROOT
from .updates import UpdateResult

def verify_update_controls(pet):
    controller=pet.updates;old_latest=controller.latest;old_voice=pet.voice
    old_preview=getattr(pet,'presentation_previews',None);old_visible=pet.bubble_visible
    try:
        pet.options.update(ignored_update_version='',update_snoozed_date='')
        pet.presentation_previews=set();pet.voice.stop()
        controller.latest=UpdateResult('available',version='99.0.0',notes='离线界面验证')
        pet.show();pet.bubble_visible=lambda:True
        shown=controller.notice.refresh() and controller.notice.isVisible()
        QApplication.processEvents()
        qa=ROOT/'qa';qa.mkdir(exist_ok=True)
        controller.notice.grab().save(str(qa/'update-notice.png'))
        pet.voice=SimpleNamespace(busy=True)
        yielded=not controller.notice.refresh() and not controller.notice.isVisible()
        pet.voice=old_voice
        returned=controller.notice.refresh() and controller.notice.isVisible()
        controller.notice.snooze_button.click()
        snoozed=not controller.notice.isVisible() and pet.options['update_snoozed_date']==date.today().isoformat()
        control=pet.preferences.controls['check_updates_periodic'];control.setChecked(False);control.setChecked(True)
        interval=pet.preferences.controls['update_interval_hours'];interval.setValue(17)
        settings=pet.options['check_updates_periodic'] and pet.options['update_interval_hours']==17
        pet.preferences.select_page('版本与更新');QApplication.processEvents()
        pet.preferences.grab().save(str(qa/'update-settings.png'))
        return dict(persistent_update_notice=shown and yielded and returned,update_snooze_check=snoozed,periodic_update_controls=settings)
    finally:
        pet.voice=old_voice;pet.presentation_previews=old_preview;pet.bubble_visible=old_visible
        controller.latest=old_latest;controller.notice.hide()
