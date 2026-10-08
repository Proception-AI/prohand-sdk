package ai.proception.glove.viewer;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.view.View;

/**
 * The taxels where they physically sit on the hand, from the glove CAD
 * drawing. Same visual language as the desktop diagnostic GUI: an Inferno
 * ramp with a pressure halo, so a press reads the same on both.
 */
final class GloveHandView extends View {

    private static final int FULL_SCALE = 4095;

    /** Below this fraction of full scale a taxel is drawn as idle, not coloured. */
    private static final float ACTIVE_THRESHOLD = 0.02f;

    /** Inferno, the diagnostic GUI's default ramp. */
    private static final int[] RAMP = {
        Color.rgb(2, 2, 12),
        Color.rgb(40, 11, 84),
        Color.rgb(85, 15, 109),
        Color.rgb(129, 37, 103),
        Color.rgb(173, 54, 83),
        Color.rgb(214, 82, 55),
        Color.rgb(243, 128, 25),
        Color.rgb(250, 186, 47),
        Color.rgb(252, 255, 164),
    };

    private final Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint rim = new Paint(Paint.ANTI_ALIAS_FLAG);

    private float[] positions = new float[0];
    private int[] values = new int[0];
    private float minX;
    private float minY;
    private float spanX = 1f;
    private float spanY = 1f;
    private float spacingMm = 1f;

    GloveHandView(Context context) {
        super(context);
        rim.setStyle(Paint.Style.STROKE);
        rim.setStrokeWidth(1.5f);
        rim.setColor(Color.argb(90, 0, 0, 0));
    }

    /** CAD positions as x,y pairs. Changing hand swaps the whole layout. */
    void setPositions(float[] xy) {
        positions = xy == null ? new float[0] : xy;
        measureLayout();
        invalidate();
    }

    void setValues(int[] taxels) {
        values = taxels;
        invalidate();
    }

    // Bounding box plus the typical neighbour distance, which sets the dot size:
    // taxel pitch varies across the hand, so a fixed radius either overlaps on
    // the fingers or looks sparse on the palm.
    private void measureLayout() {
        int count = positions.length / 2;
        if (count == 0) {
            return;
        }

        minX = Float.MAX_VALUE;
        minY = Float.MAX_VALUE;
        float maxX = -Float.MAX_VALUE;
        float maxY = -Float.MAX_VALUE;
        for (int i = 0; i < count; i++) {
            minX = Math.min(minX, positions[i * 2]);
            maxX = Math.max(maxX, positions[i * 2]);
            minY = Math.min(minY, positions[i * 2 + 1]);
            maxY = Math.max(maxY, positions[i * 2 + 1]);
        }
        spanX = Math.max(1f, maxX - minX);
        spanY = Math.max(1f, maxY - minY);

        float total = 0f;
        for (int i = 0; i < count; i++) {
            float nearest = Float.MAX_VALUE;
            for (int j = 0; j < count; j++) {
                if (i == j) {
                    continue;
                }
                float dx = positions[i * 2] - positions[j * 2];
                float dy = positions[i * 2 + 1] - positions[j * 2 + 1];
                nearest = Math.min(nearest, (float) Math.hypot(dx, dy));
            }
            total += nearest;
        }
        spacingMm = total / count;
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        int count = positions.length / 2;
        if (count == 0) {
            return;
        }

        // One scale for both axes, so the hand keeps its proportions.
        float margin = 16f;
        float scale = Math.min(
                (getWidth() - 2 * margin) / spanX,
                (getHeight() - 2 * margin) / spanY);
        float offsetX = (getWidth() - spanX * scale) / 2f;
        float offsetY = (getHeight() - spanY * scale) / 2f;
        float radius = Math.max(3f, spacingMm * scale * 0.42f);

        for (int i = 0; i < count; i++) {
            float x = offsetX + (positions[i * 2] - minX) * scale;
            float y = offsetY + (positions[i * 2 + 1] - minY) * scale;
            float level = i < values.length
                    ? Math.min(1f, Math.max(0f, values[i] / (float) FULL_SCALE))
                    : 0f;

            if (level > ACTIVE_THRESHOLD) {
                fill.setColor(rampColor(level));
                int halo = Color.argb(
                        70, Color.red(fill.getColor()),
                        Color.green(fill.getColor()),
                        Color.blue(fill.getColor()));
                int solid = fill.getColor();
                fill.setColor(halo);
                canvas.drawCircle(x, y, radius * (1.6f + 1.4f * level), fill);
                fill.setColor(solid);
            } else {
                fill.setColor(Color.rgb(55, 55, 58));
            }
            canvas.drawCircle(x, y, radius, fill);
            canvas.drawCircle(x, y, radius, rim);
        }
    }

    private static int rampColor(float level) {
        float position = Math.min(1f, Math.max(0f, level)) * (RAMP.length - 1);
        int low = (int) position;
        int high = Math.min(RAMP.length - 1, low + 1);
        float t = position - low;
        return Color.rgb(
                (int) (Color.red(RAMP[low]) + t * (Color.red(RAMP[high]) - Color.red(RAMP[low]))),
                (int) (Color.green(RAMP[low]) + t * (Color.green(RAMP[high]) - Color.green(RAMP[low]))),
                (int) (Color.blue(RAMP[low]) + t * (Color.blue(RAMP[high]) - Color.blue(RAMP[low]))));
    }
}
