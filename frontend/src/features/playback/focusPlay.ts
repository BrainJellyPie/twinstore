/** Focus the playback's Play button once it shows: a run being opened replaces the button that opened it, so focus
 *  would fall to the page. Gives up after five seconds. */
export function focusPlayWhenShown() {
  let tries = 0;
  const look = () => {
    const play = document.querySelector<HTMLElement>("[data-playback-play]");
    play?.focus();
    if (play && document.activeElement === play) return;
    if (tries++ < 50) setTimeout(look, 100);
  };
  look();
}
